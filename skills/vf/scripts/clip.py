#!/usr/bin/env python3
"""Cut a recorded check run into an MP4 for a PR, or into still frames an agent can read.

Usage:
  clip.py --check                           say what this machine can make, and how to install what's missing
  clip.py EVIDENCE_FILE                     list the run's steps and when each began
  clip.py EVIDENCE_FILE --steps 2-3         cut steps 2 through 3 into an MP4
  clip.py EVIDENCE_FILE --steps 2-3 --demo  cut a short demo to post on a PR
  clip.py EVIDENCE_FILE --frames failed     stills before, at, and after each failed step
  clip.py EVIDENCE_FILE --frames 2          stills across step 2

Reads only the evidence file in the format rules.md defines and the video it
names. A step runs from its step mark to the next one. Output lands in the
run's folder: an H.264 MP4, which GitHub, chat tools, and browsers play
inline, named for what it shows, such as
checkout-pay-step-2-customer-pays-2026-10-03-1402.mp4; or frames/*.png, one
path per line with what each shows. Cutting a clip rewrites the harness's
recordings.html so the clip is listed there.

A clip is the recording as it was, cut to the steps asked for; the clip's name
and the step list say what it shows. A demo shows a reviewer the behavior with
nothing in the way: each stretch where the picture holds still cut to a second, the last frame
held so the result stays on screen, and scaled and compressed to fit GitHub's
smallest video upload limit.

Needs ffmpeg and ffprobe, from PATH or the FFMPEG and FFPROBE variables. A clip
or a frame shows a behavior; the run's steps are the proof.

Exits 0 when the list, clip, or frames are written, or --check finds everything;
1 when --check finds something missing; 2 when it cannot run.
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _load(name, filename):
    # Loaded by path so this runs under `python3 -I`, which leaves the script's own directory off sys.path.
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replay = _load("harness_replay", "replay.py")

# Starts the clip just before the first step, so its first frame is not mid-action.
LEAD_SECONDS = 0.5
# Stills around a failed step's verdict: the action that led to it, the verdict, and what settled after.
FAILURE_OFFSETS = (-3.0, 0.0, 1.0)
FRAMES_PER_STEP = 4
# A demo keeps this much of each still stretch, so a result shows long enough to read without the wait around it.
DEMO_STILL_SECONDS = 1.0
# How different two frames may be and still count as still. Loose enough that a blinking text cursor holds still.
DEMO_STILL_NOISE = 0.003
DEMO_HOLD_SECONDS = 1.5
DEMO_MAX_WIDTH = 1280
# GitHub's smallest video upload limit, on free plans.
DEMO_MAX_BYTES = 10_000_000
DEMO_QUALITIES = ("28", "34", "40")
# H.264 in MP4 plays inline on GitHub, in chat tools, and in every browser.
# CRF 28 keeps a minute of mostly still UI to a few MB with readable text.
ENCODE = ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
# Example install commands for the optional tools, by sys.platform prefix. Agents show these; they never run them unasked.
INSTALL = {
    "ffmpeg": {"darwin": "brew install ffmpeg", "linux": "sudo apt install ffmpeg (or your package manager's ffmpeg)", "win": "winget install Gyan.FFmpeg"},
}


class ClipError(Exception):
    pass


def inside_evidence(video):
    """Whether a recording path stays inside evidence/, as rules.md requires and validate.py enforces."""
    return isinstance(video, str) and not Path(video).is_absolute() and ".." not in Path(video).parts


def objects(items):
    """The objects in an evidence list; anything else in it is skipped, as a malformed mark or step."""
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load(path):
    """The evidence file as a record, with its marks and steps reduced to objects; ClipError when it names no recording."""
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ClipError(f"cannot read {path}: {error}") from error
    recording = record.get("recording") if isinstance(record, dict) else None
    if not isinstance(recording, dict) or not recording.get("video"):
        raise ClipError(f"{path} names no recording. Rerun the check with its recording kept.")
    if not inside_evidence(recording["video"]):
        raise ClipError(f"{path} names its recording {recording['video']!r}, which is not a path inside evidence/")
    return dict(record, marks=objects(record.get("marks")), steps=objects(record.get("steps")))


def recording_start(record):
    """The run-clock time at which the video begins, so a mark's time can be turned into seconds into the video."""
    return record["recording"].get("starts_at", 0)


def steps(record):
    """The run's step marks in order, each with its seconds into the video and where it ends."""
    marks = sorted(
        (mark for mark in record.get("marks") or [] if mark.get("kind") == "step" and isinstance(mark.get("at"), (int, float))),
        key=lambda mark: mark["at"],
    )
    found = []
    for index, mark in enumerate(marks):
        end = marks[index + 1]["at"] - recording_start(record) if index + 1 < len(marks) else None
        found.append({"number": index + 1, "label": str(mark.get("label", "")), "start": max(mark["at"] - recording_start(record), 0), "end": end})
    return found


def step_window(run_steps, spec):
    """The first and last step a --steps spec names, and the video seconds to cut, starting LEAD_SECONDS early."""
    try:
        first, _, last = spec.partition("-")
        first, last = int(first), int(last or first)
    except ValueError as error:
        raise ClipError(f"--steps takes a step number or a range such as 2-3, not {spec!r}") from error
    if not run_steps:
        raise ClipError("the run has no step marks to cut by")
    if not 1 <= first <= last <= len(run_steps):
        raise ClipError(f"--steps {spec} is outside the run's steps 1-{len(run_steps)}")
    start = max(run_steps[first - 1]["start"] - LEAD_SECONDS, 0)
    return first, last, start, run_steps[last - 1]["end"]


def find_tool(name, variable):
    """The path to an ffmpeg tool, from its environment variable or PATH, or None when it is not installed."""
    return os.environ.get(variable) or shutil.which(name)


def require_tool(name, variable):
    """The path to an ffmpeg tool; ClipError when it is not installed."""
    found = find_tool(name, variable)
    if not found:
        raise ClipError(f"{name} is not installed; install ffmpeg or set {variable}")
    return found


def video_duration(ffprobe, video):
    """The video's length in seconds, read with ffprobe."""
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)], capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        raise ClipError(f"ffprobe cannot read {video}: {result.stderr.strip()}") from error


def still_stretches(ffmpeg, video, duration):
    """(start, end) of each stretch where the picture holds still longer than DEMO_STILL_SECONDS, found by ffmpeg's freezedetect."""
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(video), "-vf", f"freezedetect=n={DEMO_STILL_NOISE}:d={DEMO_STILL_SECONDS}",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ClipError(f"ffmpeg could not look for still stretches: {result.stderr.strip()}")
    starts = [float(at) for at in re.findall(r"freeze_start: ([\d.]+)", result.stderr)]
    ends = [float(at) for at in re.findall(r"freeze_end: ([\d.]+)", result.stderr)]
    # A stretch still at the end of the video gets a start and no end.
    return list(zip(starts, ends + [duration] * (len(starts) - len(ends))))


def kept_spans(stills, duration):
    """The parts of a clip a demo keeps: all of it, except each still stretch past its first DEMO_STILL_SECONDS."""
    spans, cursor = [], 0.0
    for still_start, still_end in stills:
        if still_end - still_start > DEMO_STILL_SECONDS:
            spans.append((cursor, still_start + DEMO_STILL_SECONDS))
            cursor = still_end
    spans.append((cursor, duration))
    return [(start, end) for start, end in spans if end - start > 0.05]


def demo_filter(spans):
    """Join the kept spans, scale down to DEMO_MAX_WIDTH, and hold the last frame."""
    parts = [f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[p{index}]" for index, (start, end) in enumerate(spans)]
    joined = "".join(f"[p{index}]" for index in range(len(spans))) + f"concat=n={len(spans)}:v=1:a=0"
    scale = f"scale='trunc(min({DEMO_MAX_WIDTH},iw)/2)*2':-2"
    return ";".join([*parts, f"{joined},{scale},tpad=stop_mode=clone:stop_duration={DEMO_HOLD_SECONDS}[out]"])


def encode_at(quality):
    """The ENCODE arguments with their CRF quality replaced; a higher number means a smaller, rougher file."""
    arguments = list(ENCODE)
    arguments[arguments.index("-crf") + 1] = quality
    return arguments


def run_ffmpeg(ffmpeg, arguments, scratch):
    """Run ffmpeg quietly in the scratch folder, overwriting its output; ClipError when it fails."""
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *arguments], capture_output=True, text=True, cwd=scratch)
    if result.returncode != 0:
        raise ClipError(f"ffmpeg failed: {result.stderr.strip()}")


def recorded_video(record, evidence_path):
    """Resolve a run's video from evidence/, two levels above its record."""
    video = evidence_path.resolve().parent.parent / record["recording"]["video"]
    if not video.is_file():
        raise ClipError(f"the evidence names {video}, which is not here")
    return video.resolve()


def cut_plan(evidence_path, spec, demo=False):
    """What cutting the steps spec names needs: the MP4's path in the run's folder, and ffmpeg's input arguments
    for the video window those steps cover."""
    record = load(evidence_path)
    video = recorded_video(record, evidence_path)
    run_steps = steps(record)
    first, last, start, end = step_window(run_steps, spec)
    target = evidence_path.with_suffix("") / clip_name(record, run_steps, first, last, demo)
    target.parent.mkdir(parents=True, exist_ok=True)
    window = ["-ss", f"{start:.2f}", "-i", str(video)] + (["-t", f"{end - start:.2f}"] if end is not None else [])
    return target, window


def cut(evidence_path, spec):
    """Cut the steps spec names into an MP4 in the run's folder. Returns the MP4's path."""
    target, window = cut_plan(evidence_path, spec)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch, "clip.mp4")
        run_ffmpeg(ffmpeg, [*window, "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", *ENCODE, str(output)], scratch)
        shutil.move(str(output), target)
    replay.write_recordings(replay.harness_of(evidence_path))
    return target


def demo(evidence_path, spec):
    """Cut the steps spec names into a demo MP4 in the run's folder: still stretches shortened, and small enough to post.

    Returns the MP4's path.
    """
    target, window = cut_plan(evidence_path, spec, demo=True)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    ffprobe = require_tool("ffprobe", "FFPROBE")
    with tempfile.TemporaryDirectory() as scratch:
        # Cut the window first at near-lossless quality, so still stretches are timed from the clip's start.
        steps_video = Path(scratch, "steps.mp4")
        run_ffmpeg(ffmpeg, [*window, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-an", str(steps_video)], scratch)
        duration = video_duration(ffprobe, steps_video)
        graph = demo_filter(kept_spans(still_stretches(ffmpeg, steps_video, duration), duration))
        output = Path(scratch, "demo.mp4")
        for quality in DEMO_QUALITIES:
            run_ffmpeg(ffmpeg, ["-i", str(steps_video), "-filter_complex", graph, "-map", "[out]", *encode_at(quality), str(output)], scratch)
            if output.stat().st_size <= DEMO_MAX_BYTES:
                break
        else:
            raise ClipError(
                f"the demo is {output.stat().st_size / 1e6:.1f} MB at the lowest quality, over GitHub's "
                f"{DEMO_MAX_BYTES / 1e6:g} MB upload limit; cut fewer steps"
            )
        shutil.move(str(output), target)
    replay.write_recordings(replay.harness_of(evidence_path))
    return target


def slug(text):
    """Text as a short file-name part: lowercase words joined by dashes."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "step"


def clip_name(record, run_steps, first, last, demo=False):
    """Build a shareable MP4 name from the check, steps, first label, whether it is a demo, and start time."""
    label = re.sub(r"^\s*step\s*\d+\s*[:.)-]?\s*", "", run_steps[first - 1]["label"], flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", str(record.get("started_at") or ""))
    parts = [
        slug(str(record["check"])) if record.get("check") else "",
        f"step-{first}" if first == last else f"steps-{first}-to-{last}",
        slug(label) if label.strip() else "",
        "demo" if demo else "",
        f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}-{digits[8:12]}" if len(digits) >= 12 else "",
    ]
    return "-".join(part for part in parts if part) + ".mp4"


def frame_times(record, spec):
    """(seconds into the video, file stem, what it shows) for each still the spec asks for."""
    if spec == "failed":
        found = []
        failures = [step for step in record.get("steps") or [] if step.get("passed") is False and isinstance(step.get("at"), (int, float))]
        if not failures:
            raise ClipError("the run has no failed steps with an 'at' time")
        for number, step in enumerate(failures, 1):
            at = step["at"] - recording_start(record)
            for extra in FAILURE_OFFSETS:
                seconds = max(at + extra, 0)
                when = "at the verdict" if extra == 0 else f"{abs(extra):g}s {'before' if extra < 0 else 'after'} the verdict"
                found.append((seconds, f"failed-{number}-{slug(str(step.get('name', '')))}-{seconds:.1f}s", f"Failed: {step.get('name', '')}, {when}"))
        return found
    run_steps = steps(record)
    first, last, _, end = step_window(run_steps, spec)
    begin = run_steps[first - 1]["start"]
    # The last step runs to the end of the video, whose length the evidence does not record; ffmpeg skips a time past it.
    finish = end if end is not None else begin + 10
    found = []
    for index in range(FRAMES_PER_STEP):
        seconds = begin + (finish - begin) * (index + 0.5) / FRAMES_PER_STEP
        label = run_steps[first - 1]["label"] if first == last else f"Steps {first}-{last}"
        found.append((seconds, f"steps-{first}-to-{last}-{seconds:.1f}s", f"{label}, {index + 1} of {FRAMES_PER_STEP}"))
    return found


def frames(evidence_path, spec):
    """Write the stills spec asks for into the run's frames/ folder. Returns (path, seconds, what it shows) for each one written."""
    record = load(evidence_path)
    video = recorded_video(record, evidence_path)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    # Absolute, because ffmpeg runs in a scratch directory.
    folder = evidence_path.resolve().with_suffix("") / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory() as scratch:
        for seconds, stem, label in frame_times(record, spec):
            target = folder / f"{stem}.png"
            try:
                run_ffmpeg(ffmpeg, ["-ss", f"{seconds:.2f}", "-i", str(video), "-frames:v", "1", str(target)], scratch)
            except ClipError:
                # A time past the end of the video has no frame; the others still help.
                continue
            if target.is_file():
                written.append((target, seconds, label))
    if not written:
        raise ClipError("no frame could be read at those times; the video may be shorter than the run")
    return written


def install_hint(name, platform=None):
    """An example command that installs the tool on this platform, for an agent to show, never to run unasked."""
    platform = platform or sys.platform
    commands = INSTALL[name]
    return next((command for prefix, command in commands.items() if platform.startswith(prefix)), commands["linux"])


def capabilities():
    """What this machine can make from a recording: (lines to print, whether everything is available)."""
    ffmpeg = find_tool("ffmpeg", "FFMPEG")
    ffprobe = find_tool("ffprobe", "FFPROBE")
    lines = []
    if ffmpeg and ffprobe:
        lines.append(f"Stills and clips: yes, with {ffmpeg}")
    else:
        found = " and ".join(name for name, present in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not present)
        lines.append(f"Stills and clips: no, {found} not found. Install: {install_hint('ffmpeg')}")
    lines.append("Replay pages, snapshots, and logs need none of these.")
    return lines, bool(ffmpeg and ffprobe)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, nargs="?", help="the run's evidence file, such as evidence/checkout-pay/2026-10-03T14-02-11Z.json")
    parser.add_argument("--check", action="store_true", help="say what this machine can make, and how to install what's missing")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--steps", help="a step number or range to cut into an MP4, such as 2-3")
    action.add_argument("--frames", metavar="STEP|failed", help="write stills across one step, or around each failed step")
    parser.add_argument(
        "--demo", action="store_true",
        help="with --steps, cut a demo to post on a PR: still stretches cut to a second, last frame held, under GitHub's upload limit",
    )
    args = parser.parse_args()
    if args.check:
        lines, complete = capabilities()
        print("\n".join(lines))
        return 0 if complete else 1
    if args.evidence is None:
        parser.error("give an evidence file, or --check")
    if args.demo and not args.steps:
        parser.error("--demo needs --steps")
    try:
        if args.frames:
            for path, seconds, label in frames(args.evidence, args.frames):
                print(f"{path}  {seconds:.1f}s  {label}")
        elif args.demo:
            print(demo(args.evidence, args.steps))
        elif args.steps:
            print(cut(args.evidence, args.steps))
        else:
            for step in steps(load(args.evidence)):
                end = "end" if step["end"] is None else f"{step['end']:.1f}s"
                print(f"{step['number']:>3}  {step['start']:6.1f}s-{end:<7}  {step['label']}")
        return 0
    except (ClipError, OSError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
