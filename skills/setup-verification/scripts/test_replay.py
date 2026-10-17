import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("replay.py")
SPEC = importlib.util.spec_from_file_location("verification_replay", SCRIPT)
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)

RECORD = {
    "check": "checkout-pay",
    "sub_features": ["checkout.pay"],
    "passed": False,
    "code": {"app": {"commit": "a1b2c3d4e5f6", "dirty": True}},
    "started_at": "2026-10-03T14:02:11Z",
    "steps": [
        {"name": "order is created", "passed": True, "at": 9.0},
        {"name": "order is paid", "passed": False, "at": 21.4, "detail": "status=pending", "evidence": {"order_id": "o_1"},
         "snapshot": {"screenshot": "checkout-pay-1/step-1-failed.png", "text": "checkout-pay-1/step-1-failed.txt"}},
    ],
    "marks": [
        {"at": 1.0, "kind": "action", "label": "Opens the store before recording"},
        {"at": 3.0, "kind": "step", "label": "Step 1: Customer pays"},
        {"at": 4.2, "kind": "action", "label": "Clicks Pay </script><b>"},
    ],
    "recording": {"video": "checkout-pay-1/video.webm", "starts_at": 2.0},
    "stopped": None,
}


def write(directory, record):
    path = Path(directory) / "evidence" / "checkout-pay-1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(record))
    return path


def data(page):
    start = page.index('<script type="application/json" id="data">') + len('<script type="application/json" id="data">')
    return json.loads(page[start:page.index("</script>", start)])


class ReplayTest(unittest.TestCase):
    def test_page_sits_in_the_run_folder_and_times_entries_from_the_video(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = write(directory, RECORD)
            target, video = replay.write_replay(evidence)
            self.assertEqual(target, evidence.parent / "checkout-pay-1" / "replay.html")
            page = target.read_text()
            self.assertIn('src="video.webm"', page)
            self.assertIn("Failed.", page)
            self.assertIn("app a1b2c3d (uncommitted changes)", page)
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
            target, _ = replay.write_replay(evidence, Path(directory) / "share" / "page.html")
            page = target.read_text()
            self.assertIn('src="../evidence/checkout-pay-1/video.webm"', page)
            failed = [entry for entry in data(page)["timeline"] if entry["kind"] == "fail"]
            self.assertEqual(failed[0]["snapshot"]["screenshot"], "../evidence/checkout-pay-1/step-1-failed.png")

    def test_step_text_cannot_close_the_data_script(self):
        with tempfile.TemporaryDirectory() as directory:
            target, _ = replay.write_replay(write(directory, RECORD))
            page = target.read_text()
            self.assertNotIn("</script><b>", page)
            self.assertIn("Clicks Pay </script><b>", [entry["label"] for entry in data(page)["timeline"]])

    def test_run_without_a_recording_gets_the_timeline_alone(self):
        record = {key: value for key, value in RECORD.items() if key != "recording"}
        with tempfile.TemporaryDirectory() as directory:
            target, video = replay.write_replay(write(directory, record))
            page = target.read_text()
            self.assertIsNone(video)
            self.assertNotIn("<video", page)
            self.assertIn("kept no recording", page)
            self.assertTrue(all(entry["video_at"] is None for entry in data(page)["timeline"]))

    def test_marks_and_steps_that_are_not_objects_are_skipped(self):
        record = dict(RECORD, marks=RECORD["marks"] + ["Clicks Pay"], steps=RECORD["steps"] + [7])
        with tempfile.TemporaryDirectory() as directory:
            target, _ = replay.write_replay(write(directory, record))
            labels = [entry["label"] for entry in data(target.read_text())["timeline"]]
            self.assertEqual(labels.count("Clicks Pay"), 0)
            self.assertIn("order is paid", labels)

    def test_a_recording_outside_evidence_stops(self):
        for video in ("../video.webm", "/tmp/video.webm"):
            with self.subTest(video=video), tempfile.TemporaryDirectory() as directory:
                evidence = write(directory, dict(RECORD, recording={"video": video, "starts_at": 2.0}))
                result = subprocess.run([sys.executable, str(SCRIPT), str(evidence)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("not a path inside evidence/", result.stderr)
                self.assertFalse((evidence.parent / "checkout-pay-1" / "replay.html").exists())

    def test_verdict_names_stopped_and_unjudged_runs(self):
        self.assertEqual(replay.verdict({"passed": None, "stopped": "app crashed"})[0], "Stopped")
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

    def test_help_runs_without_evidence(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("replay page", result.stdout)


if __name__ == "__main__":
    unittest.main()
