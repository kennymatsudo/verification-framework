import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

SPEC = importlib.util.spec_from_file_location("verification_demo", SCRIPTS / "demo.py")
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe")
CODE = {"app": {"commit": "abc123", "dirty_hash": None}}
HARNESS = {"harness.json": "h1", "scripts/drive.py": "d1"}


def demo_record(**changes):
    record = {
        "check": "checkout-demo", "demo": True, "accepted_by": "vf.py run", "passed": True,
        "sub_features": ["checkout.pay"], "started_at": "2026-11-06T14:02:11Z", "finished_at": "2026-11-06T14:03:00Z",
        "code": CODE, "harness_code": dict(HARNESS, **{"demos/checkout/run.py": "r1"}),
        "steps": [{"name": "the confirmation shows", "passed": True, "at": 6.0}],
        "marks": [
            {"at": 1.0, "kind": "action", "label": "Switches to shopper", "screen": "Shopper view"},
            {"at": 2.0, "kind": "step", "label": "Step 1: sign in", "caption": "The shopper signs in"},
            {"at": 4.0, "kind": "step", "label": "Step 2: pays", "caption": "The shopper pays"},
            {"at": 5.0, "kind": "action", "label": "Waits", "caption": "Waiting for the payment"},
            {"at": 6.0, "kind": "action", "label": "Switches to staff", "screen": "Staff view"},
            {"at": 7.0, "kind": "step", "label": "Step 3: staff see it", "caption": "Staff see the order"},
        ],
        "recording": {"video": "demos/checkout-demo/1/shopper.mp4", "starts_at": 0.0, "screen": "Shopper view"},
        "recordings": [
            {"video": "demos/checkout-demo/1/shopper.mp4", "starts_at": 0.0, "screen": "Shopper view"},
            {"video": "demos/checkout-demo/1/staff.mp4", "starts_at": 0.5, "screen": "Staff view"},
        ],
    }
    record.update(changes)
    return record


def check_record(**changes):
    record = {"check": "checkout-pay", "accepted_by": "vf.py run", "passed": True, "planned_break": None,
              "sub_features": ["checkout.pay"], "finished_at": "2026-11-06T13:00:00Z", "code": CODE,
              "harness_code": dict(HARNESS, **{"scripts/checks/pay.py": "c1"}), "steps": []}
    record.update(changes)
    return record


def harness_with(directory, demo_changes=None, checks=()):
    root = Path(directory)
    (root / "rules.md").write_text("# Verification rules\n")
    evidence = root / "evidence"
    path = evidence / "demos" / "checkout-demo" / "1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(demo_record(**(demo_changes or {}))))
    for index, record in enumerate(checks):
        check = evidence / record["check"] / f"{index}.json"
        check.parent.mkdir(parents=True, exist_ok=True)
        check.write_text(json.dumps(record))
    return path


class ProofTest(unittest.TestCase):
    def proof(self, *checks, **demo_changes):
        with tempfile.TemporaryDirectory() as directory:
            path = harness_with(directory, demo_changes, checks)
            return demo.proof(demo.load(path), path.parent.parent.parent)

    def test_a_pass_on_the_same_code_proves_the_demo(self):
        self.assertEqual(self.proof(check_record()), [("checkout.pay", "evidence/checkout-pay/0.json", None)])

    def test_no_pass_a_failed_latest_run_and_other_code_do_not(self):
        self.assertEqual(self.proof()[0][2], "no ordinary run covers it yet")
        failed = check_record(passed=False, finished_at="2026-11-06T13:30:00Z")
        self.assertEqual(self.proof(check_record(), failed)[0][2], "its latest ordinary run did not pass")
        moved = check_record(code={"app": {"commit": "def456", "dirty_hash": None}})
        self.assertIn("different code", self.proof(moved)[0][2])

    def test_a_shared_harness_file_that_changed_breaks_the_link_but_the_demo_itself_does_not(self):
        changed = check_record(harness_code=dict(HARNESS, **{"scripts/drive.py": "d2"}))
        self.assertIn("harness file changed", self.proof(changed)[0][2])
        self.assertIsNone(self.proof(check_record())[0][2], "the demo's own file and the check's entry are not shared")

    def test_a_planned_break_is_never_the_proof(self):
        broken = check_record(planned_break={"what": "x"}, passed=False, finished_at="2026-11-06T13:30:00Z")
        self.assertIsNone(self.proof(check_record(), broken)[0][2])

    def test_a_record_outside_evidence_demos_or_not_a_demo_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "evidence", "checkout-demo", "1.json")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(demo_record()))
            with self.assertRaisesRegex(demo.DemoError, "not under evidence/demos"):
                demo.load(path)
            path.write_text(json.dumps(demo_record(demo=False)))
            with self.assertRaisesRegex(demo.DemoError, "not a demo run"):
                demo.load(path)


class RangeTest(unittest.TestCase):
    def test_a_range_runs_from_just_before_its_first_step_to_the_next_step(self):
        first, last, start, end = demo.step_range(demo_record(), "1-2")
        self.assertEqual((first["number"], last["number"], start, end), (1, 2, 1.5, 7.0))
        self.assertIsNone(demo.step_range(demo_record(), "3")[3], "the last step runs to the end of the recording")

    def test_a_step_without_a_caption_cannot_be_shown(self):
        record = demo_record()
        del record["marks"][2]["caption"]
        with self.assertRaisesRegex(demo.DemoError, "step 2 .* has no caption"):
            demo.step_range(record, "1-3")
        demo.step_range(record, "3")

    def test_screens_switch_at_screen_marks_with_no_gap(self):
        record = dict(demo_record(), recordings=demo_record()["recordings"])
        self.assertEqual(demo.segments(record, 1.5, None), [("Shopper view", 1.5, 6.0), ("Staff view", 6.0, None)])
        self.assertEqual(demo.segments(record, 6.5, 9.0), [("Staff view", 6.5, 9.0)])

    def test_a_switch_to_an_unrecorded_screen_or_an_unknown_first_screen_stops(self):
        record = demo_record()
        record["marks"][4]["screen"] = "Expert view"
        with self.assertRaisesRegex(demo.DemoError, "no recording"):
            demo.segments(record, 1.5, None)
        with self.assertRaisesRegex(demo.DemoError, "screen is unknown"):
            demo.segments(demo_record(), 0.5, None)

    def test_one_video_needs_no_screen_names(self):
        record = demo_record(recordings=[{"video": "demos/checkout-demo/1/video.mp4", "starts_at": 0.0}])
        self.assertEqual(demo.segments(record, 0.0, None), [(None, 0.0, None)])


@unittest.skipUnless(FFMPEG and FFPROBE, "needs ffmpeg and ffprobe")
class VideoTest(unittest.TestCase):
    def make(self, directory, color, name, seconds=12):
        video = Path(directory, "evidence", "demos", "checkout-demo", "1", name)
        video.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"color=c={color}:size=320x240:rate=25:duration={seconds}", "-pix_fmt", "yuv420p", str(video)],
                       check=True)

    def length(self, path):
        result = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                                capture_output=True, text=True, check=True)
        return float(json.loads(result.stdout)["format"]["duration"])

    def color_at(self, video, seconds, directory):
        still = Path(directory, f"still-{seconds}.rgb")
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(seconds), "-i", str(video),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(still)], check=True)
        red, green, blue = still.read_bytes()[:3]
        return "red" if red > 200 and green < 60 else "blue" if blue > 200 and red < 60 else "other"

    def test_the_video_keeps_real_time_and_switches_screens_at_the_same_moment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = harness_with(directory, checks=[check_record()])
            self.make(directory, "red", "shopper.mp4")
            self.make(directory, "blue", "staff.mp4")
            maker = demo.Maker(path, 10_000_000)
            videos, stills = maker.make("1-3")
            [(video, seconds, _)] = videos
            self.assertEqual(video.name, "checkout-demo-steps-1-to-3-2026-11-06-1402.mp4")
            # From just before step 1 (1.5 s) to where the first video to end runs out (12 s), with nothing removed.
            self.assertAlmostEqual(self.length(video), 10.5, delta=0.3)
            self.assertAlmostEqual(seconds, 10.5, delta=0.1)
            self.assertEqual(self.color_at(video, 2.0, directory), "red", "the shopper's screen before the switch")
            self.assertEqual(self.color_at(video, 6.0, directory), "blue", "the staff screen after it, at 6.0 s of run time")
            shown = [what for _, _, what in stills]
            self.assertIn("caption 'Waiting for the payment' on 'Shopper view'", shown)
            self.assertIn("switch to 'Staff view'", shown)
            self.assertTrue(all(still.is_file() for still, _, _ in stills))
            self.assertIn("checkout-demo-steps-1-to-3", Path(directory, "recordings.html").read_text())

    def test_a_video_over_the_limit_splits_at_step_marks_and_never_inside_a_step(self):
        with tempfile.TemporaryDirectory() as directory:
            path = harness_with(directory, {"recordings": [{"video": "demos/checkout-demo/1/video.mp4", "starts_at": 0.0}]},
                                checks=[check_record()])
            self.make(directory, "red", "video.mp4")
            maker = demo.Maker(path, 1)
            maker.max_bytes = 1
            with self.assertRaisesRegex(demo.DemoError, "alone is .* never cuts inside a step"):
                maker.make("1-3")
            maker.max_bytes = 10_000_000
            whole, _ = maker.make("1-3")
            maker.max_bytes = whole[0][2] - 1
            # One quality only, so the smaller encodings can't bring the whole video under the limit.
            qualities, demo.QUALITIES = demo.QUALITIES, ("20",)
            try:
                parts, _ = maker.make("1-3")
            finally:
                demo.QUALITIES = qualities
            names = [video.name for video, _, _ in parts]
            self.assertGreater(len(parts), 1, names)
            self.assertTrue(all(f"-of-{len(parts)}-" in name for name in names), names)
            self.assertAlmostEqual(sum(seconds for _, seconds, _ in parts), whole[0][1], delta=0.2,
                                   msg="the parts together cover exactly the steps, with nothing removed")

    def test_a_demo_no_check_covers_still_makes_its_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path = harness_with(directory, {"sub_features": [],
                                            "recordings": [{"video": "demos/checkout-demo/1/video.mp4", "starts_at": 0.0}]})
            self.make(directory, "red", "video.mp4")
            [(video, _, _)], _ = demo.Maker(path, 10_000_000).make("1-3")
            self.assertTrue(video.is_file())
            self.assertNotIn("Ordinary passing runs", "\n".join(demo.listing(path)))

if __name__ == "__main__":
    unittest.main()
