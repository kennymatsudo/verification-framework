#!/usr/bin/env python3
"""Cut a recorded check run into an MP4 for a PR, or into still frames an agent can read.

Usage:
  clip.py --check                           say what this machine can make, and how to install what's missing
  clip.py EVIDENCE_FILE                     list the run's steps and when each began
  clip.py EVIDENCE_FILE --steps 2-3         cut steps 2 through 3 into an MP4
  clip.py EVIDENCE_FILE --steps 2-3 --demo  cut a short, captioned demo to post on a PR
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
smallest video upload limit. A demo also carries numbered captions, one per
step and action mark in the window, each shown until the next, so a reviewer
can tell what the run did from what the app did on its own.

Needs ffmpeg and ffprobe, from PATH or the FFMPEG and FFPROBE variables.
Captions are drawn with ffmpeg's drawtext filter when the build has it, else
with Pillow when it is installed; with neither, a demo has no captions and
says so. A clip or a frame shows a behavior; the run's steps are the proof.

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
# Captions sit above the bottom edge, where apps often keep an input bar, in a dark box sized to the video.
CAPTION_HEIGHT_SHARE = 1 / 30
CAPTION_BOTTOM_SHARE = 0.17
CAPTION_WRAP = 60
# Bold fonts tried for Pillow captions, in order, before its built-in font.
CAPTION_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
# H.264 in MP4 plays inline on GitHub, in chat tools, and in every browser.
# CRF 28 keeps a minute of mostly still UI to a few MB with readable text.
ENCODE = ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
# Example install commands for the optional tools, by sys.platform prefix. Agents show these; they never run them unasked.
INSTALL = {
    "ffmpeg": {"darwin": "brew install ffmpeg", "linux": "sudo apt install ffmpeg (or your package manager's ffmpeg)", "win": "winget install Gyan.FFmpeg"},
    "pillow": {"darwin": "python3 -m pip install pillow", "linux": "python3 -m pip install pillow", "win": "py -m pip install pillow"},
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


def captions(record, start, end):
    """(from, until, text) for each step and action mark in the video window [start, end), in seconds into the
    window, numbered in order. A mark repeating the one before it is dropped, and of marks at the same moment only
    the last is kept, since the others would show for no time. The last caption runs to the end, shown as None."""
    found = []
    for mark in sorted((mark for mark in record.get("marks") or [] if mark.get("kind") in ("step", "action")
                        and isinstance(mark.get("at"), (int, float)) and str(mark.get("label", "")).strip()),
                       key=lambda mark: mark["at"]):
        at = mark["at"] - recording_start(record) - start
        label = str(mark["label"]).strip()
        if at < 0 or (end is not None and at >= end - start) or (found and found[-1][1] == label):
            continue
        if found and found[-1][0] == max(at, 0.0):
            found.pop()
        found.append((max(at, 0.0), label))
    return [(at, found[index + 1][0] if index + 1 < len(found) else None, f"{index + 1}. {label}")
            for index, (at, label) in enumerate(found)]


def caption_renderer(ffmpeg):
    """How this machine draws captions: "drawtext" when ffmpeg has that filter, else "pillow" when Pillow is
    installed, else None."""
    result = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    if re.search(r"^\s*\S+\s+drawtext\s", result.stdout, flags=re.MULTILINE):
        return "drawtext"
    return "pillow" if importlib.util.find_spec("PIL") else None


def shown_while(since, until):
    """An ffmpeg enable expression for a caption shown from since until until, or to the end when until is None."""
    return f"gte(t,{since:.3f})" if until is None else f"between(t,{since:.3f},{until:.3f})"


def wrapped(text):
    """A caption broken into lines of about CAPTION_WRAP characters, so a long mark fits the frame."""
    import textwrap
    return "\n".join(textwrap.wrap(text, CAPTION_WRAP)) or text


def drawtext_chain(caption_list, scratch):
    """The drawtext filters that draw each caption, centered above the bottom edge in a dark box. Each caption's
    text goes in a file, so no character in a mark needs escaping."""
    filters = []
    for index, (since, until, text) in enumerate(caption_list):
        textfile = Path(scratch, f"caption-{index}.txt")
        textfile.write_text(wrapped(text))
        filters.append(
            f"drawtext=textfile={textfile.name}:fontcolor=white:fontsize=h*{CAPTION_HEIGHT_SHARE:.4f}:box=1:"
            f"boxcolor=black@0.85:boxborderw=18:x=(w-text_w)/2:y=h*(1-{CAPTION_BOTTOM_SHARE})-text_h:"
            f"enable='{shown_while(since, until)}'"
        )
    return ",".join(filters)


def caption_images(caption_list, width, height, scratch):
    """Draw each caption with Pillow as a transparent PNG as wide as the video: white bold text in a dark rounded
    box, centered. Returns the image paths, in caption order."""
    from PIL import Image, ImageDraw, ImageFont  # Optional: only a demo on a machine without drawtext needs it.
    size = max(int(height * CAPTION_HEIGHT_SHARE), 12)
    font = next((ImageFont.truetype(path, size) for path in CAPTION_FONTS if Path(path).is_file()), None)
    font = font or ImageFont.load_default(size=size)
    paths = []
    for index, (_, _, text) in enumerate(caption_list):
        lines = wrapped(text).split("\n")
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        line_height = size + size // 3
        text_width = max(probe.textlength(line, font=font) for line in lines)
        pad = size * 3 // 4
        box_height = line_height * len(lines) + pad * 2
        image = Image.new("RGBA", (width, box_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        left = (width - text_width) / 2
        draw.rounded_rectangle([left - pad, 0, left + text_width + pad, box_height - 1], radius=pad // 2, fill=(20, 20, 20, 225))
        for number, line in enumerate(lines):
            draw.text(((width - probe.textlength(line, font=font)) / 2, pad + number * line_height), line, font=font,
                      fill=(255, 255, 255, 255))
        path = Path(scratch, f"caption-{index}.png")
        image.save(path)
        paths.append(path)
    return paths


def overlay_chain(caption_list):
    """The overlay filters that lay each caption image (inputs 1 onward) over the video while its caption shows."""
    filters, source = [], "[0:v]"
    for index, (since, until, _) in enumerate(caption_list):
        label = f"[c{index}]"
        filters.append(f"{source}[{index + 1}:v]overlay=x=0:y=H*(1-{CAPTION_BOTTOM_SHARE})-h:enable='{shown_while(since, until)}'{label}")
        source = label
    return filters, source


def demo_filter(spans, captioned=None):
    """Join the kept spans, scale down to DEMO_MAX_WIDTH, and hold the last frame. captioned is (filters, label):
    filters that caption the video and the label of their output, which the spans are then cut from."""
    prefix, source = [], "[0:v]"
    if captioned and captioned[0]:
        filters, label = captioned
        prefix = [*filters, f"{label}split={len(spans)}" + "".join(f"[s{index}]" for index in range(len(spans)))]
        source = None
    parts = [f"{source or f'[s{index}]'}trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[p{index}]"
             for index, (start, end) in enumerate(spans)]
    joined = "".join(f"[p{index}]" for index in range(len(spans))) + f"concat=n={len(spans)}:v=1:a=0"
    scale = f"scale='trunc(min({DEMO_MAX_WIDTH},iw)/2)*2':-2"
    return ";".join([*prefix, *parts, f"{joined},{scale},tpad=stop_mode=clone:stop_duration={DEMO_HOLD_SECONDS}[out]"])


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
    """What cutting the steps spec names needs: the MP4's path in the run's folder, ffmpeg's input arguments
    for the video window those steps cover, and the captions for that window."""
    record = load(evidence_path)
    video = recorded_video(record, evidence_path)
    run_steps = steps(record)
    first, last, start, end = step_window(run_steps, spec)
    target = evidence_path.with_suffix("") / clip_name(record, run_steps, first, last, demo)
    target.parent.mkdir(parents=True, exist_ok=True)
    window = ["-ss", f"{start:.2f}", "-i", str(video)] + (["-t", f"{end - start:.2f}"] if end is not None else [])
    return target, window, captions(record, start, end)


def cut(evidence_path, spec):
    """Cut the steps spec names into an MP4 in the run's folder. Returns the MP4's path."""
    target, window, _ = cut_plan(evidence_path, spec)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch, "clip.mp4")
        run_ffmpeg(ffmpeg, [*window, "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", *ENCODE, str(output)], scratch)
        shutil.move(str(output), target)
    replay.write_recordings(replay.harness_of(evidence_path))
    return target


def video_size(ffprobe, video):
    """The video's (width, height), read with ffprobe."""
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(video)],
        capture_output=True, text=True,
    )
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as error:
        raise ClipError(f"ffprobe cannot read {video}'s size: {result.stderr.strip()}") from error


def demo(evidence_path, spec):
    """Cut the steps spec names into a demo MP4 in the run's folder: captioned, still stretches shortened, and small
    enough to post.

    Returns the MP4's path and a note when it could not draw captions, else None.
    """
    target, window, caption_list = cut_plan(evidence_path, spec, demo=True)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    ffprobe = require_tool("ffprobe", "FFPROBE")
    with tempfile.TemporaryDirectory() as scratch:
        # Cut the window first at near-lossless quality, so still stretches are timed from the clip's start.
        steps_video = Path(scratch, "steps.mp4")
        run_ffmpeg(ffmpeg, [*window, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-an", str(steps_video)], scratch)
        duration = video_duration(ffprobe, steps_video)
        renderer = caption_renderer(ffmpeg) if caption_list else None
        inputs, captioned, note = ["-i", str(steps_video)], None, None
        if caption_list and renderer == "drawtext":
            chain = drawtext_chain(caption_list, scratch)
            captioned = ([f"[0:v]{chain}[captioned]"], "[captioned]")
        elif caption_list and renderer == "pillow":
            width, height = video_size(ffprobe, steps_video)
            images = caption_images(caption_list, width, height, scratch)
            inputs += [argument for image in images for argument in ("-i", str(image))]
            captioned = overlay_chain(caption_list)
        elif caption_list:
            note = f"no captions: this ffmpeg has no drawtext filter and Pillow is not installed. Install: {install_hint('pillow')}"
        graph = demo_filter(kept_spans(still_stretches(ffmpeg, steps_video, duration), duration), captioned)
        output = Path(scratch, "demo.mp4")
        for quality in DEMO_QUALITIES:
            run_ffmpeg(ffmpeg, [*inputs, "-filter_complex", graph, "-map", "[out]", *encode_at(quality), str(output)], scratch)
            if output.stat().st_size <= DEMO_MAX_BYTES:
                break
        else:
            raise ClipError(
                f"the demo is {output.stat().st_size / 1e6:.1f} MB at the lowest quality, over GitHub's "
                f"{DEMO_MAX_BYTES / 1e6:g} MB upload limit; cut fewer steps"
            )
        shutil.move(str(output), target)
    replay.write_recordings(replay.harness_of(evidence_path))
    return target, note


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
    if ffmpeg:
        renderer = caption_renderer(ffmpeg)
        if renderer:
            lines.append(f"Demo captions: yes, with {'ffmpeg drawtext' if renderer == 'drawtext' else 'Pillow'}")
        else:
            lines.append(f"Demo captions: no, this ffmpeg has no drawtext filter and Pillow is not installed. Install: {install_hint('pillow')}")
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
        help="with --steps, cut a demo to post on a PR: captioned with the run's marks, still stretches cut to a second, "
             "last frame held, under GitHub's upload limit",
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
            path, note = demo(args.evidence, args.steps)
            print(path)
            if note:
                print(note, file=sys.stderr)
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
