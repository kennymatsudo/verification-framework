import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "clip.py"
SPEC = importlib.util.spec_from_file_location("verification_clip", SCRIPT)
clip = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clip)

RECORD = {
    "check": "checkout-pay",
    "passed": False,
    "steps": [{"name": "order is paid", "passed": False, "at": 7.0}],
    "marks": [
        {"at": 2.0, "kind": "step", "label": "Step 1: Customer fills the cart"},
        {"at": 3.0, "kind": "action", "label": "Adds a shirt"},
        {"at": 5.0, "kind": "step", "label": "Step 2: Customer pays"},
        {"at": 6.0, "kind": "action", "label": "Clicks Pay"},
        {"at": 8.0, "kind": "step", "label": "Step 3: Customer sees the receipt"},
    ],
    "recording": {"video": "checkout-pay/1/video.mp4", "starts_at": 1.0},
}
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe")


class StepsTest(unittest.TestCase):
    def test_steps_run_from_their_mark_to_the_next_in_video_time(self):
        found = clip.steps(RECORD)
        self.assertEqual([(step["number"], step["start"], step["end"]) for step in found], [(1, 1.0, 4.0), (2, 4.0, 7.0), (3, 7.0, None)])

    def test_pick_leads_in_and_rejects_steps_the_run_lacks(self):
        found = clip.steps(RECORD)
        self.assertEqual(clip.step_window(found, "2"), (2, 2, 3.5, 7.0))
        self.assertEqual(clip.step_window(found, "2-3"), (2, 3, 3.5, None))
        for spec in ("0", "4", "3-2", "two"):
            with self.subTest(spec=spec), self.assertRaises(clip.ClipError):
                clip.step_window(found, spec)

    def test_clip_names_say_what_they_show_on_their_own(self):
        run_steps = clip.steps(RECORD)
        started = dict(RECORD, started_at="2026-10-03T14:02:11Z")
        self.assertEqual(clip.clip_name(started, run_steps, 2, 2), "checkout-pay-step-2-customer-pays-2026-10-03-1402.mp4")
        self.assertEqual(clip.clip_name(started, run_steps, 1, 3), "checkout-pay-steps-1-to-3-customer-fills-the-cart-2026-10-03-1402.mp4")
        self.assertEqual(clip.clip_name(started, run_steps, 2, 2, demo=True), "checkout-pay-step-2-customer-pays-demo-2026-10-03-1402.mp4")
        unnumbered = [dict(run_steps[0], label="Adds an item to the cart")]
        self.assertEqual(clip.clip_name({"check": "cart-add"}, unnumbered, 1, 1), "cart-add-step-1-adds-an-item-to-the-cart.mp4")

    def test_a_demo_keeps_the_first_second_of_each_long_still_stretch(self):
        self.assertEqual(clip.kept_spans([], 5.0), [(0.0, 5.0)])
        self.assertEqual(clip.kept_spans([(1.0, 4.0), (5.0, 5.8)], 8.0), [(0.0, 2.0), (4.0, 8.0)], "a short still stays whole")
        self.assertEqual(clip.kept_spans([(2.0, 8.0)], 8.0), [(0.0, 3.0)], "a still that runs to the end is cut after its first second")

    def test_demo_captions_number_each_mark_in_the_window_until_the_next(self):
        _, _, start, end = clip.step_window(clip.steps(RECORD), "2-3")
        self.assertEqual(clip.captions(RECORD, start, end), [
            (0.5, 1.5, "1. Step 2: Customer pays"),
            (1.5, 3.5, "2. Clicks Pay"),
            (3.5, None, "3. Step 3: Customer sees the receipt"),
        ])

    def test_demo_captions_drop_a_mark_that_repeats_the_one_before_and_marks_outside_the_window(self):
        record = dict(RECORD, marks=[
            {"at": 5.0, "kind": "step", "label": "Step 2: Customer pays"},
            {"at": 5.0, "kind": "action", "label": "Step 2: Customer pays"},
            {"at": 6.0, "kind": "note", "label": "not a step or an action"},
            {"at": 6.5, "kind": "action", "label": "  "},
            {"at": 9.0, "kind": "action", "label": "after the window"},
        ])
        self.assertEqual(clip.captions(record, 3.5, 7.0), [(0.5, None, "1. Step 2: Customer pays")])

    def test_demo_captions_keep_the_last_of_marks_at_the_same_moment(self):
        record = dict(RECORD, marks=[
            {"at": 5.0, "kind": "step", "label": "Step 2: Customer pays"},
            {"at": 5.0, "kind": "action", "label": "Goes to the payment page"},
            {"at": 6.0, "kind": "action", "label": "Clicks Pay"},
        ])
        self.assertEqual(clip.captions(record, 3.5, None), [(0.5, 1.5, "1. Goes to the payment page"), (1.5, None, "2. Clicks Pay")])

    def test_a_captioned_demo_cuts_its_spans_from_the_captioned_video(self):
        graph = clip.demo_filter([(0.0, 1.0), (2.0, 3.0)], (["[0:v]drawtext=textfile=caption-0.txt[captioned]"], "[captioned]"))
        self.assertIn("[captioned]split=2[s0][s1]", graph)
        self.assertIn("[s0]trim=start=0.000:end=1.000", graph)
        self.assertIn("[s1]trim=start=2.000:end=3.000", graph)
        self.assertNotIn("[0:v]trim", graph)
        self.assertTrue(clip.demo_filter([(0.0, 1.0)]).startswith("[0:v]trim"), "an uncaptioned demo cuts the video itself")

    def test_drawtext_captions_read_their_text_from_files_and_show_until_the_next(self):
        with tempfile.TemporaryDirectory() as scratch:
            chain = clip.drawtext_chain([(0.5, 1.5, "1. Clicks 'Pay': 100%"), (1.5, None, "2. Sees the receipt")], scratch)
            self.assertEqual(Path(scratch, "caption-0.txt").read_text(), "1. Clicks 'Pay': 100%")
        self.assertIn("textfile=caption-0.txt", chain)
        self.assertIn("enable='between(t,0.500,1.500)'", chain)
        self.assertIn("enable='gte(t,1.500)'", chain)

    def test_overlay_captions_lay_each_image_in_order(self):
        filters, label = clip.overlay_chain([(0.5, 1.5, "a"), (1.5, None, "b")])
        self.assertEqual(label, "[c1]")
        self.assertTrue(filters[0].startswith("[0:v][1:v]overlay"))
        self.assertTrue(filters[1].startswith("[c0][2:v]overlay"))

    def test_check_says_how_demo_captions_are_drawn(self):
        for renderer, line in (("drawtext", "Demo captions: yes, with ffmpeg drawtext"), ("pillow", "Demo captions: yes, with Pillow")):
            with self.subTest(renderer=renderer), patch.object(clip, "find_tool", return_value="/bin/ffmpeg"), \
                    patch.object(clip, "caption_renderer", return_value=renderer):
                self.assertIn(line, clip.capabilities()[0])
        with patch.object(clip, "find_tool", return_value="/bin/ffmpeg"), patch.object(clip, "caption_renderer", return_value=None), \
                patch.object(clip.sys, "platform", "darwin"):
            self.assertIn("Demo captions: no, this ffmpeg has no drawtext filter and Pillow is not installed. "
                          "Install: python3 -m pip install pillow", clip.capabilities()[0])

    def test_frames_across_a_step_are_spread_inside_it(self):
        times = [round(seconds, 2) for seconds, _, _ in clip.frame_times(RECORD, "2")]
        self.assertEqual(times, [4.38, 5.12, 5.88, 6.62])
        with self.assertRaises(clip.ClipError):
            clip.frame_times(dict(RECORD, steps=[]), "failed")

    def test_check_reports_what_is_missing_with_the_install_line_for_this_platform(self):
        with patch.object(clip.shutil, "which", return_value=None), patch.dict(os.environ, {}, clear=True), patch.object(clip.sys, "platform", "darwin"):
            lines, complete = clip.capabilities()
        self.assertFalse(complete)
        self.assertIn("Stills and clips: no, ffmpeg and ffprobe not found. Install: brew install ffmpeg", lines)
        self.assertIn("Replay pages, snapshots, and logs need none of these.", lines)

    def test_install_hints_cover_each_platform(self):
        self.assertEqual(clip.install_hint("ffmpeg", "win32"), "winget install Gyan.FFmpeg")
        self.assertTrue(clip.install_hint("ffmpeg", "freebsd13").startswith("sudo apt"), "an unknown platform gets the generic line")

    def test_check_exits_1_when_something_is_missing_and_needs_no_evidence(self):
        env = dict(os.environ, PATH="/nonexistent")
        env.pop("FFMPEG", None)
        env.pop("FFPROBE", None)
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--check"], capture_output=True, text=True, env=env)
        self.assertIn("Stills and clips: no", result.stdout)
        self.assertEqual(result.returncode, 1)

    def test_marks_and_steps_that_are_not_objects_are_skipped(self):
        record = dict(RECORD, marks=RECORD["marks"] + ["Clicks Pay", 7], steps=RECORD["steps"] + [None])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps(record))
            loaded = clip.load(path)
            self.assertEqual(clip.steps(loaded), clip.steps(RECORD))
            self.assertEqual(clip.frame_times(loaded, "failed"), clip.frame_times(RECORD, "failed"))

    def test_a_recording_outside_evidence_stops(self):
        for video in ("../video.mp4", "/tmp/video.mp4"):
            with self.subTest(video=video), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "run.json"
                path.write_text(json.dumps(dict(RECORD, recording={"video": video, "starts_at": 1.0})))
                with self.assertRaisesRegex(clip.ClipError, "not a path inside evidence/"):
                    clip.load(path)

    def test_evidence_without_a_recording_stops_with_the_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"steps": []}))
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("names no recording", result.stderr)


@unittest.skipUnless(FFMPEG and FFPROBE, "needs ffmpeg and ffprobe")
class CutTest(unittest.TestCase):
    def make_run(self, directory, source="testsrc=size=320x240:rate=10:duration=10"):
        (Path(directory) / "rules.md").write_text("# Verification rules\n")
        evidence = Path(directory) / "evidence" / "checkout-pay" / "1.json"
        video = evidence.with_suffix("") / "video.mp4"
        video.parent.mkdir(parents=True)
        subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", source,
             "-pix_fmt", "yuv420p", str(video)],
            check=True,
        )
        evidence.write_text(json.dumps(RECORD))
        return evidence

    def probe(self, path):
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        )
        info = json.loads(result.stdout)
        return info["streams"][0]["width"], info["streams"][0]["height"], float(info["format"]["duration"])

    def test_cut_keeps_the_frame_and_the_steps_length(self):
        with tempfile.TemporaryDirectory() as directory:
            target = clip.cut(self.make_run(directory), "2")
            self.assertEqual(target.name, "checkout-pay-step-2-customer-pays.mp4")
            self.assertIn(f'href="evidence/checkout-pay/1/{target.name}"', (Path(directory) / "recordings.html").read_text())
            width, height, duration = self.probe(target)
            self.assertEqual((width, height), (320, 240))
            self.assertAlmostEqual(duration, 3.5, delta=0.3)

    def test_a_demo_drops_the_still_wait_and_holds_the_result(self):
        # Moves for 4 seconds, then holds still for 6.
        source = "testsrc=size=320x240:rate=10:duration=4,tpad=stop_mode=clone:stop_duration=6"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(clip, "caption_renderer", return_value=None):
                target, note = clip.demo(self.make_run(directory, source), "2-3")
            self.assertEqual(target.name, "checkout-pay-steps-2-to-3-customer-pays-demo.mp4")
            self.assertIn("no captions", note)
            width, height, duration = self.probe(target)
            self.assertEqual((width, height), (320, 240))
            # 0.5 seconds moving, 1 second of the still stretch, then the held last frame, instead of 6.5 seconds.
            expected = 0.5 + clip.DEMO_STILL_SECONDS + clip.DEMO_HOLD_SECONDS
            self.assertAlmostEqual(duration, expected, delta=0.3)

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "needs Pillow to draw and read the caption")
    def test_a_demo_drawn_with_pillow_shows_the_caption_on_the_video(self):
        from PIL import Image
        source = "color=c=white:size=320x240:rate=10:duration=10"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(clip, "caption_renderer", return_value="pillow"):
                target, note = clip.demo(self.make_run(directory, source), "2-3")
            self.assertIsNone(note)
            still = Path(directory, "still.png")
            subprocess.run([FFMPEG, "-v", "error", "-ss", "0.8", "-i", str(target), "-frames:v", "1", str(still)], check=True)
            # The caption's dark box sits centered just above the bottom of a white frame.
            box = Image.open(still).convert("RGB").getpixel((160, int(240 * (1 - clip.CAPTION_BOTTOM_SHARE)) - 4))
            self.assertLess(max(box), 80)

    def test_frames_around_a_failure_land_in_the_run_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            written = clip.frames(self.make_run(directory), "failed")
            self.assertEqual([round(seconds, 1) for _, seconds, _ in written], [3.0, 6.0, 7.0])
            self.assertTrue(all(path.parent.name == "frames" and path.is_file() for path, _, _ in written))
            self.assertEqual(written[1][2], "Failed: order is paid, at the verdict")

    def test_frames_past_the_end_of_the_video_are_skipped(self):
        record = dict(RECORD, steps=[{"name": "late", "passed": False, "at": 12.0}])
        with tempfile.TemporaryDirectory() as directory:
            evidence = self.make_run(directory)
            evidence.write_text(json.dumps(record))
            written = clip.frames(evidence, "failed")
            self.assertEqual([round(seconds, 1) for _, seconds, _ in written], [8.0])


if __name__ == "__main__":
    unittest.main()
