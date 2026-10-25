import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "replay.py"
SPEC = importlib.util.spec_from_file_location("verification_replay", SCRIPT)
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)
NODE = shutil.which("node")

RECORD = {
    "check": "checkout-pay",
    "sub_features": ["checkout.pay"],
    "passed": False,
    "code": {"app": {"commit": "a1b2c3d4e5f6", "dirty": True}},
    "started_at": "2026-10-03T14:02:11Z",
    "steps": [
        {"name": "order is created", "passed": True, "at": 9.0},
        {"name": "order is paid", "passed": False, "at": 21.4, "detail": "status=pending", "evidence": {"order_id": "o_1"},
         "snapshot": {"screenshot": "checkout-pay/1/step-1-failed.png", "text": "checkout-pay/1/step-1-failed.txt"}},
    ],
    "marks": [
        {"at": 1.0, "kind": "action", "label": "Opens the store before recording"},
        {"at": 3.0, "kind": "step", "label": "Step 1: Customer pays"},
        {"at": 4.2, "kind": "action", "label": "Clicks Pay </script><b>"},
    ],
    "recording": {"video": "checkout-pay/1/video.webm", "starts_at": 2.0},
    "stopped": None,
}


def write(directory, record):
    """An evidence file in a harness at directory, marked as one by its rules.md."""
    (Path(directory) / "rules.md").write_text("# Verification rules\n")
    path = Path(directory) / "evidence" / "checkout-pay" / "1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record))
    return path


def data(page):
    start = page.index('<script type="application/json" id="data">') + len('<script type="application/json" id="data">')
    return json.loads(page[start:page.index("</script>", start)])


class ReplayTest(unittest.TestCase):
    def test_overlapping_page_writes_publish_complete_files_without_colliding(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "recordings.html"
            target.write_text("previous page")
            publishing = threading.Barrier(2)
            replace = Path.replace

            def publish_together(source, destination):
                self.assertEqual(target.read_text(), "previous page")
                publishing.wait(timeout=5)
                return replace(source, destination)

            pages = ["first complete page", "second complete page"]
            with patch.object(Path, "replace", publish_together), ThreadPoolExecutor(max_workers=2) as writers:
                list(writers.map(lambda text: replay.write_atomically(target, text), pages))

            self.assertIn(target.read_text(), pages)
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_failed_page_publication_keeps_the_previous_page_and_removes_its_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "recordings.html"
            target.write_text("previous page")

            with patch.object(Path, "replace", side_effect=OSError("cannot publish")):
                with self.assertRaisesRegex(OSError, "cannot publish"):
                    replay.write_atomically(target, "new page")

            self.assertEqual(target.read_text(), "previous page")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_page_sits_in_the_run_folder_and_times_entries_from_the_video(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            target, video, _ = replay.write_replay(evidence)
            self.assertEqual(target, evidence.with_suffix("") / "replay.html")
            page = target.read_text()
            self.assertIn('src="video.webm"', page)
            self.assertIn('<span class="badge failed">Failed</span> <span><span class="muted">Failed step: </span>order is paid', page)
            self.assertIn("app a1b2c3d (local edits)", page)
            entries = data(page)["timeline"]
            self.assertEqual([entry["label"] for entry in entries][:2], ["Opens the store before recording", "Step 1: Customer pays"])
            self.assertIsNone(entries[0]["video_at"], "a mark before the recording began cannot be played")
            failed = [entry for entry in entries if entry["kind"] == "fail"]
            self.assertEqual(failed[0]["video_at"], 19.4)
            self.assertEqual(failed[0]["detail"], "status=pending")
            self.assertEqual(failed[0]["snapshot"], {"screenshot": "step-1-failed.png", "text": "step-1-failed.txt"})

    def test_page_written_elsewhere_links_files_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            target, _, _ = replay.write_replay(evidence, Path(directory) / "share" / "page.html")
            page = target.read_text()
            self.assertIn('src="../evidence/checkout-pay/1/video.webm"', page)
            failed = [entry for entry in data(page)["timeline"] if entry["kind"] == "fail"]
            self.assertEqual(failed[0]["snapshot"]["screenshot"], "../evidence/checkout-pay/1/step-1-failed.png")

    def test_step_text_cannot_close_the_data_script(self):
        with tempfile.TemporaryDirectory() as directory:
            target, _, _ = replay.write_replay(write(directory, RECORD))
            page = target.read_text()
            self.assertNotIn("</script><b>", page)
            self.assertIn("Clicks Pay </script><b>", [entry["label"] for entry in data(page)["timeline"]])

    def test_run_without_a_recording_gets_the_timeline_alone(self):
        record = {key: value for key, value in RECORD.items() if key != "recording"}
        with tempfile.TemporaryDirectory() as directory:
            target, video, _ = replay.write_replay(write(directory, record))
            page = target.read_text()
            self.assertIsNone(video)
            self.assertNotIn("<video", page)
            self.assertIn("No video was kept for this run.", page)
            self.assertIn('<div class="layout novideo">', page, "nothing to put beside the steps, so one column")
            self.assertTrue(all(entry["video_at"] is None for entry in data(page)["timeline"]))

    def test_marks_and_steps_that_are_not_objects_are_skipped(self):
        record = dict(RECORD, marks=RECORD["marks"] + ["Clicks Pay"], steps=RECORD["steps"] + [7])
        with tempfile.TemporaryDirectory() as directory:
            target, _, _ = replay.write_replay(write(directory, record))
            labels = [entry["label"] for entry in data(target.read_text())["timeline"]]
            self.assertEqual(labels.count("Clicks Pay"), 0)
            self.assertIn("order is paid", labels)

    def test_a_recording_outside_evidence_stops(self):
        for video in ("../video.webm", "/tmp/video.webm"):
            with self.subTest(video=video), tempfile.TemporaryDirectory() as directory:
                evidence = write(directory, dict(RECORD, recording={"video": video, "starts_at": 2.0}))
                with self.assertRaisesRegex(replay.ReplayError, "not a path inside evidence/"):
                    replay.write_replay(evidence)
                self.assertFalse((evidence.with_suffix("") / "replay.html").exists())

    def test_verdict_names_unfinished_and_unjudged_runs(self):
        self.assertEqual(replay.verdict({"passed": None, "stopped": "app crashed"})[0], "Didn't finish")
        self.assertEqual(replay.verdict({"passed": False, "stopped": "app crashed"})[0], "Didn't finish", "a stop outranks earlier failures")
        self.assertEqual(replay.verdict({"passed": None})[0], "No verdict")
        self.assertEqual(replay.verdict({"passed": True})[0], "Passed")

    def test_command_exits_2_on_unreadable_evidence_and_warns_on_a_missing_video(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text("{")
            result = subprocess.run([sys.executable, str(SCRIPT), str(bad)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("STOPPED: cannot read", result.stderr)

            evidence = write(directory, RECORD)
            result = subprocess.run([sys.executable, str(SCRIPT), str(evidence)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("WARN the evidence names", result.stderr)

    def test_recordings_page_lists_every_run_and_builds_each_ones_replay_page(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            folder = evidence.with_suffix("")
            folder.mkdir()
            (folder / "checkout-pay-step-1-customer-pays-2026-10-03-1402.mp4").write_bytes(b"")
            unrecorded = {key: value for key, value in RECORD.items() if key != "recording"}
            (evidence.parents[1] / "orders-api").mkdir()
            (evidence.parents[1] / "orders-api" / "1.json").write_text(json.dumps(dict(unrecorded, check="orders-api")))
            (evidence.parent / "notes.json").write_text("{")

            replay.write_replay(evidence)
            recordings = (evidence.parents[2] / "recordings.html").read_text()
            self.assertIn('id="check-orders-api"', recordings, "a run with no video is listed too")
            self.assertTrue((evidence.parents[1] / "orders-api" / "1" / "replay.html").is_file(), "every listed run gets a replay page")
            orders = recordings[recordings.index('id="check-orders-api"'):]
            orders = orders[:orders.index("</article>")]
            self.assertNotIn("Watch", orders, "nothing to watch without a video")
            self.assertIn("No video kept", orders)
            self.assertIn('href="evidence/orders-api/1/replay.html">Open the run</a>', orders)
            self.assertIn('href="evidence/checkout-pay/1/checkout-pay-step-1-customer-pays-2026-10-03-1402.mp4"', recordings)
            self.assertIn(">Clip: step 1</a>", recordings)
            self.assertNotIn(">Video<", recordings, "the raw video is reached from its replay page")

    def test_the_launch_record_is_not_listed_as_a_check_run(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            launch = evidence.parents[1] / "launch" / "record.json"
            launch.parent.mkdir()
            launch.write_text(json.dumps({"command": ["python3", "app.py"], "pid": 123, "started_at": "2026-10-20T10:00:00Z"}))
            self.assertEqual([path for path, _ in replay.listed_runs(evidence.parents[1])], [evidence])

    def test_replay_page_links_back_to_the_recordings_page_and_to_its_video_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target, _, _ = replay.write_replay(write(directory, RECORD))
            page = target.read_text()
            self.assertIn('href="../../../recordings.html">&larr; All check runs', page)
            self.assertIn('<a href="video.webm">Open the video file</a>', page)

    def test_recordings_page_gives_each_check_one_line_for_its_latest_run_failing_first(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, check="cart-add", passed=True, started_at="2026-10-05T10:00:00Z"))
            for day in range(1, 5):
                record = dict(RECORD, passed=day != 4, started_at=f"2026-10-0{day}T10:00:00Z")
                (evidence.parent / f"{day + 1}.json").write_text(json.dumps(record))
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertEqual(recordings.count("<article "), 2, "one line per check, not per run")
            self.assertLess(recordings.index('id="check-checkout-pay"'), recordings.index('id="check-cart-add"'), "its latest run failed")
            details = recordings[recordings.index('id="check-checkout-pay-details"'):]
            self.assertEqual(details[:details.index("</article>")].count('class="dot '), 3, "its three earlier runs are in its details")
            self.assertIn('data-result="failed" aria-pressed="false">Failed <span>1</span>', recordings)
            self.assertIn('data-result="passed" aria-pressed="false">Passed <span>1</span>', recordings)

    def test_details_list_only_the_newest_earlier_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            for number in range(replay.HISTORY_RUNS + 2):
                (evidence.parent / f"old-{number}.json").write_text(json.dumps(dict(RECORD, started_at=f"2026-09-{number + 1:02d}T10:00:00Z")))
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertEqual(recordings.count('class="dot '), replay.HISTORY_RUNS)
            self.assertIn("2 older runs in <code>evidence/checkout-pay/</code>.", recordings)

    def test_planned_breaks_are_left_out_and_counted_in_a_footnote(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, passed=True, started_at="2026-10-01T10:00:00Z"))
            broken = dict(RECORD, planned_break={"what": "payment skipped", "sub_features": ["checkout.pay"]})
            (evidence.parent / "2.json").write_text(json.dumps(broken))
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertIn('class="badge passed">Passed</span>', recordings, "the break's failure doesn't stand in for the latest run")
            self.assertNotIn('class="dot ', recordings, "nor does it show in the history")
            self.assertIn("1 run that broke the code on purpose is left out; ", recordings)

    def test_details_list_the_behaviors_the_run_judged_in_their_wording(self):
        with tempfile.TemporaryDirectory() as directory:
            steps = [
                {"name": "order is created", "passed": True, "at": 9.0, "sub_features": ["checkout.pay"]},
                {"name": "order is listed", "passed": False, "at": 12.0, "sub_features": ["checkout.unlisted"]},
            ]
            evidence = write(directory, dict(RECORD, steps=steps, sub_features=["checkout.pay", "checkout.unlisted", "checkout.refund"]))
            features = Path(directory) / "features"
            features.mkdir()
            (features / "checkout.md").write_text(
                "# Checkout\n\nA shopper pays.\n\n## Sub-features\n\n- checkout.pay: paying with a new card creates a paid order.\n\n"
                "## How to prove it\n\n- checkout.pay: `bin/verify check checkout-pay`.\n"
            )
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertIn('<h2>Checkout <span class="slug">checkout-pay</span></h2>', recordings)
            self.assertIn('</h2><p class="purpose">A shopper pays.</p>', recordings, "the feature's summary says what the check tests")
            unlisted = '<li class="fail" title="checkout.unlisted"><span class="icon">✕</span><span class="name">checkout.unlisted</span>'
            self.assertIn(unlisted, recordings, "an ID with no wording shows as itself")
            # Each behavior names the step that judged it and the moment in the video, 3 seconds early.
            paid = ('<span class="name">Paying with a new card creates a paid order.</span> <span class="muted">· order is created '
                    '<span class="time">0:07</span> <a class="watch" href="evidence/checkout-pay/1/replay.html#at=4">Watch</a></span>')
            self.assertIn(paid, recordings)
            refund = '<span class="name">checkout.refund</span> <span class="muted">· not judged by any step that ran</span>'
            self.assertIn(refund, recordings)
            self.assertLess(recordings.index(unlisted), recordings.index(paid), "failed behaviors first")
            self.assertLess(recordings.index(paid), recordings.index(refund), "then passed, then not judged")
            self.assertNotIn("bin/verify", recordings, "only Sub-features lines are wording")
            searchable = recordings[recordings.index('data-search="') + len('data-search="'):]
            self.assertIn("paying with a new card creates a paid order", searchable[:searchable.index('"')])
            subprocess.run([sys.executable, str(SCRIPT), evidence.name], cwd=evidence.parent, check=True, capture_output=True)
            self.assertIn("Paying with a new card", (evidence.parents[2] / "recordings.html").read_text(), "run from inside its check folder")
            page = (evidence.with_suffix("") / "replay.html").read_text()
            self.assertIn('<h1>Checkout <span class="slug">checkout-pay</span></h1>', page, "the replay page is titled like the list")

    def test_a_feature_summary_is_its_first_plain_sentence(self):
        with tempfile.TemporaryDirectory() as directory:
            features = Path(directory) / "features"
            features.mkdir()
            (features / "cart.md").write_text(
                "# Cart\n\nA shopper calls `add_item` from\nthe [cart page](cart.md). The cart keeps it.\n\n## Sub-features\n"
            )
            self.assertEqual(replay.feature_metadata(Path(directory))[0][:2], ("Cart", "A shopper calls add_item from the cart page."))

    def test_details_say_so_when_no_step_names_the_behaviors_it_judges(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, sub_features=["checkout.pay", "checkout.refund"]))
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertIn("<h3>Behaviors this check covers</h3>", recordings)
            self.assertIn("so the run can't say which passed.", recordings)
            self.assertNotIn("not judged by any step", recordings)

    def test_a_step_naming_no_sub_feature_judges_a_check_covering_one(self):
        self.assertEqual(replay.behavior_results(RECORD), [("checkout.pay", "failed")])
        several = dict(RECORD, sub_features=["checkout.pay", "checkout.refund"])
        self.assertEqual(replay.behavior_results(several), [("checkout.pay", "not judged"), ("checkout.refund", "not judged")])

    def test_recordings_page_leaves_a_current_replay_page_alone_and_rebuilds_an_older_one(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            existing = evidence.with_suffix("") / "replay.html"
            existing.parent.mkdir()
            current = f'<meta name="replay-format" content="{replay.REPLAY_FORMAT}">kept'
            existing.write_text(current)
            replay.write_recordings(evidence.parents[2])
            self.assertEqual(existing.read_text(), current)

            existing.write_text("built before the page had a format")
            replay.write_recordings(evidence.parents[2])
            self.assertIn(f'content="{replay.REPLAY_FORMAT}"', existing.read_text())
            self.assertIn("get('at')", existing.read_text(), "the rebuilt page opens at a Watch link's moment")

    def test_evidence_outside_a_harness_writes_its_replay_page_but_no_recordings_page(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "somewhere" / "evidence" / "checkout-pay" / "1.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps(RECORD))
            target, _, recordings = replay.write_replay(evidence)
            self.assertTrue(target.is_file())
            self.assertIsNone(recordings)
            self.assertEqual(list(Path(directory).rglob("recordings.html")), [])
            result = subprocess.run([sys.executable, str(SCRIPT), "--recordings", str(Path(directory) / "somewhere")],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("is not a harness", result.stderr)

    def test_missing_repo_metadata_still_renders_both_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, code={"app": None}))
            target, _, _ = replay.write_replay(evidence)
            self.assertIn("app ?", target.read_text())
            recordings = (Path(directory) / "recordings.html").read_text()
            self.assertIn('<th scope="row" title="app">app</th>', recordings)
            self.assertIn('class="commit">?</td>', recordings)

    def test_invalid_code_metadata_stops_without_publishing_a_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, code=["app"]))
            with self.assertRaisesRegex(replay.ReplayError, "code metadata"):
                replay.write_replay(evidence)
            self.assertFalse((evidence.with_suffix("") / "replay.html").exists())

    def test_a_failed_check_leads_with_its_first_failed_step_and_watches_from_just_before_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-shop"
            evidence = harness / "evidence" / "checkout-pay" / "1.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps(RECORD))
            recordings = replay.recordings_page(harness)
            self.assertIn('<h1>shop</h1>\n<p class="meta">1 check · last run <time datetime="2026-10-03T14:02:11Z">', recordings)
            self.assertIn('class="badge failed">Failed</span>', recordings)
            self.assertIn('<p class="what"><span class="muted">Failed step: </span>order is paid</p>', recordings)
            self.assertIn('<p class="note">1 of 2 steps failed · ', recordings)
            self.assertIn('<p class="code">app a1b2c3d (local edits)</p>', recordings, "the line names the code it ran on")
            # The failed step is 19.4s into the video; the link starts the replay a few seconds before it.
            self.assertIn('href="evidence/checkout-pay/1/replay.html#at=16.4">Watch the failure</a>', recordings)
            self.assertIn("<h3>Steps</h3>", recordings)
            self.assertIn('<li class="fail"><span class="icon">✕</span><span class="name">order is paid</span> <span class="time">0:19</span> '
                          '<a class="watch" href="evidence/checkout-pay/1/replay.html#at=16.4">Watch</a><pre>status=pending</pre></li>', recordings)
            self.assertIn('<li class="pass"><span class="icon">✓</span><span class="name">order is created</span> <span class="time">0:07</span> '
                          '<a class="watch" href="evidence/checkout-pay/1/replay.html#at=4">Watch</a></li>', recordings,
                          "a passed step shows the moment it was decided too")
            searchable = recordings[recordings.index('data-search="') + len('data-search="'):]
            for word in ("checkout.pay", "order is paid", "a1b2c3d", "failed"):
                self.assertIn(word, searchable[:searchable.index('"')])

    def test_a_run_that_didnt_finish_says_it_has_no_verdict_and_what_failed_before_it_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, stopped="the browser failed"))
            recordings = replay.recordings_page(evidence.parents[2])
            self.assertIn('class="badge stopped">Didn&#x27;t finish</span>', recordings)
            self.assertIn('<p class="what"><span class="muted">Stopped: </span>the browser failed</p>', recordings)
            self.assertIn('<p class="note">Stopped after 2 steps, 1 failed · ', recordings)
            self.assertIn("Watch where it stopped</a>", recordings)
            self.assertIn("<h3>Why it stopped</h3><pre>the browser failed</pre>", recordings)
            self.assertIn('data-result="stopped" aria-pressed="false">Didn&#x27;t finish <span>1</span>', recordings)
            self.assertNotIn('data-result="failed"', recordings, "a result no check has gets no filter")

    def test_code_is_one_aligned_line_per_repo_naming_only_what_is_unusual(self):
        code = {
            "app": {"commit": "a1b2c3d4", "branch": "feature/very-long-branch-name", "dirty": True, "on_main": False},
            "worker": {"commit": "e5f6a7b8", "dirty": False, "on_main": True},
        }
        cell = replay.code_cells(dict(RECORD, code=code))
        self.assertEqual(cell.count('<tr><th scope="row"'), 2)
        app_row = cell[cell.index(">app<"):cell.index(">worker<")]
        self.assertIn("local edits", app_row)
        self.assertIn("not on main", app_row)
        worker_row = cell[cell.index(">worker<"):]
        self.assertNotIn("local edits", worker_row)
        self.assertNotIn("not on main", worker_row)
        self.assertIn('title="Checked out at a commit, not on a branch">no branch</td>', worker_row)

    def test_each_check_names_the_code_its_latest_run_tested(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, dict(RECORD, started_at="2026-10-04T10:00:00Z"))
            older = dict(RECORD, check="orders-api", started_at="2026-10-02T10:00:00Z",
                         code={"app": {"commit": "ffff000", "branch": "main", "dirty": False}})
            (evidence.parents[1] / "orders-api").mkdir()
            (evidence.parents[1] / "orders-api" / "1.json").write_text(json.dumps(older))
            recordings = replay.recordings_page(evidence.parents[2])
            orders = recordings[recordings.index('id="check-orders-api"'):]
            self.assertIn('<p class="code">app main ffff000</p>', orders)
            self.assertIn('<p class="code">app a1b2c3d (local edits)</p>', recordings[:recordings.index('id="check-orders-api"')])
            self.assertIn("app main ffff000", orders[orders.index('data-search="'):orders.index('">')], "a commit is searchable")

    @unittest.skipUnless(NODE, "needs Node.js to execute replay JavaScript")
    def test_replay_page_opens_at_its_links_moment_or_else_just_before_the_first_failure(self):
        page = replay.page(RECORD, "video.webm")
        script = page.rsplit("<script>", 1)[1].split("</script>", 1)[0]
        driver = """
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
// Any DOM call the page makes besides the video's returns another stand-in, so the script runs whole.
const stub = () => new Proxy(function () {}, {
  get(target, key) {
    if (key === Symbol.toPrimitive) return () => 0;
    if (key === Symbol.iterator) return function* () {};
    if (!(key in target)) target[key] = stub();
    return target[key];
  },
  apply: () => stub(),
});
const answers = input.cases.map(({hash, readyState}) => {
  const listeners = [];
  const video = {
    currentTime: 7, readyState, duration: NaN, paused: true, play() {},
    addEventListener: (event, callback) => { if (event === 'loadedmetadata') listeners.push(callback); },
  };
  const elements = {data: {textContent: JSON.stringify(input.data)}, video};
  const document = stub();
  document.getElementById = (id) => elements[id] || stub();
  vm.runInNewContext(input.script, {document, location: {hash}, URLSearchParams});
  const beforeMetadata = video.currentTime;
  listeners.forEach((callback) => callback());
  return {beforeMetadata, afterMetadata: video.currentTime};
});
process.stdout.write(JSON.stringify(answers));
"""
        cases = [
            {"hash": "#at=16.4", "readyState": 1},
            {"hash": "#at=16.4", "readyState": 0},
            {"hash": "#at=-3", "readyState": 1},
            {"hash": "#at=invalid", "readyState": 1},
            {"hash": "", "readyState": 1},
        ]
        result = subprocess.run(
            [NODE, "-e", driver], input=json.dumps({"script": script, "data": data(page), "cases": cases}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        # The failure is 19.4s into the video, so with no usable link the page waits 3 seconds before it.
        self.assertEqual(json.loads(result.stdout), [
            {"beforeMetadata": 16.4, "afterMetadata": 16.4},
            {"beforeMetadata": 7, "afterMetadata": 16.4},
            {"beforeMetadata": 0, "afterMetadata": 0},
            {"beforeMetadata": 16.4, "afterMetadata": 16.4},
            {"beforeMetadata": 16.4, "afterMetadata": 16.4},
        ])

    def test_clip_labels_name_the_steps_they_show(self):
        self.assertEqual(replay.clip_label("checkout-pay-step-2-customer-pays-2026-10-03-1402.mp4"), "Clip: step 2")
        self.assertEqual(replay.clip_label("checkout-pay-steps-2-to-3-customer-pays.mp4"), "Clip: steps 2-3")
        self.assertEqual(replay.clip_label("demo.mp4"), "Clip")

    def test_recordings_page_says_when_no_check_has_run(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-shop"
            harness.mkdir()
            # Setup copies rules.md into a new harness before it creates this page.
            (harness / "rules.md").write_text("# Verification rules\n")
            result = subprocess.run([sys.executable, str(SCRIPT), "--recordings", str(harness)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str((harness / "recordings.html").resolve()))
            page = (harness / "recordings.html").read_text()
            self.assertIn("No check has run yet.", page)
            self.assertIn("VERIFY_KEEP_RECORDING=1", page)

    def test_help_runs_without_evidence(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("replay page", result.stdout)


if __name__ == "__main__":
    unittest.main()
