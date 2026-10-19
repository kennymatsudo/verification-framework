#!/usr/bin/env python3
"""Cut a recorded check run into a captioned MP4 for a PR, or into still frames an agent can read.

Usage:
  clip.py --check                           say what this machine can make, and how to install what's missing
  clip.py EVIDENCE_FILE                     list the run's steps and when each began
  clip.py EVIDENCE_FILE --steps 2-3         cut steps 2 through 3 into an MP4
  clip.py EVIDENCE_FILE --steps 2 --no-captions
  clip.py EVIDENCE_FILE --frames failed     stills before, at, and after each failed step
  clip.py EVIDENCE_FILE --frames 2          stills across step 2

Reads only the evidence file in the format rules.md defines and the video it
names. A step runs from its step mark to the next one. Output lands in the
run's folder: an H.264 MP4, which GitHub, chat tools, and browsers play
inline, named for what it shows, such as
checkout-pay-step-2-customer-pays-2026-10-03-1402.mp4; or frames/*.png, one
path per line with what each shows. Cutting a clip rewrites the harness's
recordings.html so the clip is listed there.

A clip's caption bar sits under the page and names each step and action as
it happens, and each failed step as a problem at its moment. Captions are
drawn by a headless Chrome, Chromium, or Edge (the CHROME variable, then
Playwright's headless shell, then the usual install locations, then
Playwright's full browsers) and laid over the
video by ffmpeg. With no browser, an ffmpeg with the subtitles filter draws
them instead. With neither, pass --no-captions. Frames need no captions.

Needs ffmpeg and ffprobe, from PATH or the FFMPEG and FFPROBE variables. A clip
or a frame shows a behavior; the run's steps are the proof.

Exits 0 when the list, clip, or frames are written, or --check finds everything;
1 when --check finds something missing; 2 when it cannot run.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import util
from pathlib import Path

# Starts the clip just before the first step, so its first frame is not mid-action.
LEAD_SECONDS = 0.5
# How long a failed step's problem caption stays on screen.
PROBLEM_SECONDS = 3
# Stills around a failed step's verdict: the action that led to it, the verdict, and what settled after.
FAILURE_OFFSETS = (-3.0, 0.0, 1.0)
FRAMES_PER_STEP = 4
CAPTION_HEIGHT = 64
FONT_SIZE = 26
BROWSER_SECONDS = 60
# H.264 in MP4 plays inline on GitHub, in chat tools, and in every browser.
# CRF 28 keeps a minute of mostly still UI to a few MB with readable text.
ENCODE = ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
BROWSER_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge"]
BROWSER_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
PLAYWRIGHT_CACHES = ["~/Library/Caches/ms-playwright", "~/.cache/ms-playwright", "%LOCALAPPDATA%/ms-playwright"]
# Prefer the headless shell to avoid macOS window registration failures in sandboxed sessions.
PLAYWRIGHT_HEADLESS_SHELLS = ["chrome-headless-shell", "chrome-headless-shell.exe"]
PLAYWRIGHT_BROWSERS = ["chrome", "chrome.exe", "Chromium"]
# Example install commands for the optional tools, by sys.platform prefix. Agents show these; they never run them unasked.
INSTALL = {
    "ffmpeg": {"darwin": "brew install ffmpeg", "linux": "sudo apt install ffmpeg (or your package manager's ffmpeg)", "win": "winget install Gyan.FFmpeg"},
    "browser": {"darwin": "brew install --cask google-chrome", "linux": "sudo apt install chromium (or your package manager's Chromium)", "win": "winget install Google.Chrome"},
}
NO_CAPTIONS_HINT = (
    "Install Chrome or Chromium, or set CHROME to one; or set FFMPEG to an ffmpeg with the subtitles filter; "
    "or pass --no-captions"
)


class ClipError(Exception):
    pass


def inside_evidence(video):
    """Whether a recording path stays inside evidence/, as rules.md requires and validate.py enforces."""
    return isinstance(video, str) and not Path(video).is_absolute() and ".." not in Path(video).parts


def objects(items):
    """The objects in an evidence list; anything else in it is skipped, as a malformed mark or step."""
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load(path):
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


def offset(record):
    return record["recording"].get("starts_at", 0)


def steps(record):
    """The run's step marks in order, each with its seconds into the video and where it ends."""
    marks = sorted(
        (mark for mark in record.get("marks") or [] if mark.get("kind") == "step" and isinstance(mark.get("at"), (int, float))),
        key=lambda mark: mark["at"],
    )
    found = []
    for index, mark in enumerate(marks):
        end = marks[index + 1]["at"] - offset(record) if index + 1 < len(marks) else None
        found.append({"number": index + 1, "label": str(mark.get("label", "")), "start": max(mark["at"] - offset(record), 0), "end": end})
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


def cues(record, start, end):
    """Captions for the window, in seconds from the clip's start: the current step or action, and each problem."""
    timed = sorted(
        (mark["at"] - offset(record), str(mark.get("label", "")))
        for mark in record.get("marks") or []
        if isinstance(mark.get("at"), (int, float))
    )
    found = []
    for index, (at, label) in enumerate(timed):
        # A cue lasts until the next mark; the last one stays up for 30 seconds.
        until = timed[index + 1][0] if index + 1 < len(timed) else at + 30
        if end is not None:
            until = min(until, end)
        if until > max(at, start):
            found.append((max(at, start) - start, until - start, label, False))
    for step in record.get("steps") or []:
        at = step.get("at")
        if step.get("passed") is False and isinstance(at, (int, float)):
            at -= offset(record)
            if at >= start and (end is None or at < end):
                found.append((at - start, at - start + PROBLEM_SECONDS, f"Problem: {step.get('name', '')}", True))
    return found


def find_tool(name, variable):
    return os.environ.get(variable) or shutil.which(name)


def require_tool(name, variable):
    found = find_tool(name, variable)
    if not found:
        raise ClipError(f"{name} is not installed; install ffmpeg or set {variable}")
    return found


def find_browser():
    """A Chromium-family browser that can screenshot a page headless, or None."""
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    shell = playwright_browser(PLAYWRIGHT_HEADLESS_SHELLS)
    if shell:
        return shell
    for name in BROWSER_NAMES:
        if shutil.which(name):
            return shutil.which(name)
    for path in BROWSER_PATHS:
        if Path(path).is_file():
            return path
    return playwright_browser(PLAYWRIGHT_BROWSERS)


def playwright_browser(binaries):
    """The first of these executables in a Playwright browser cache, newest build first, or None."""
    for cache in PLAYWRIGHT_CACHES:
        root = Path(os.path.expandvars(os.path.expanduser(cache)))
        if not root.is_dir():
            continue
        for build in sorted(root.glob("chromium*"), reverse=True):
            for binary in binaries:
                for path in build.glob(f"**/{binary}"):
                    if path.is_file() and os.access(path, os.X_OK):
                        return str(path)
    return None


def can_caption_with_ffmpeg(ffmpeg):
    result = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    return any(line.split()[1:2] == ["subtitles"] for line in result.stdout.splitlines() if line.strip())


def video_size(ffprobe, video):
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(video)],
        capture_output=True, text=True,
    )
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return stream["width"] // 2 * 2, stream["height"] // 2 * 2
    except (json.JSONDecodeError, KeyError, IndexError) as error:
        raise ClipError(f"ffprobe cannot read {video}: {result.stderr.strip()}") from error


def captions_page(texts, width):
    """Every caption as a bar of its own, stacked, so one screenshot renders them all."""
    bars = "".join(
        f'<div style="height:{CAPTION_HEIGHT}px;padding:0 24px;display:flex;align-items:center;justify-content:center;'
        f'overflow:hidden;white-space:nowrap;background:{"#b3261e" if problem else "#111"};color:#fff;'
        f'font:{"600 " if problem else ""}{FONT_SIZE}px system-ui,-apple-system,Segoe UI,sans-serif">{html.escape(text)}</div>'
        for text, problem in texts
    )
    return f'<!doctype html><meta charset="utf-8"><body style="margin:0;width:{width}px">{bars}</body>'


def render_captions(browser, texts, width, scratch):
    """Screenshot the stacked caption bars in one headless browser launch."""
    page = Path(scratch, "captions.html")
    page.write_text(captions_page(texts, width))
    image = Path(scratch, "captions.png")
    command = [
        browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
        # A profile of its own keeps the run away from the developer's open browser and its tabs.
        f"--user-data-dir={Path(scratch, 'profile')}", "--force-device-scale-factor=1",
        f"--window-size={width},{CAPTION_HEIGHT * len(texts)}", f"--screenshot={image}", page.as_uri(),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, timeout=BROWSER_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipError(f"{browser} could not render captions: {error}. {NO_CAPTIONS_HINT}") from error
    if not image.is_file():
        raise ClipError(f"{browser} wrote no caption image. {NO_CAPTIONS_HINT}")
    return image


def overlay_filter(caption_cues, width, height):
    """Pad a caption bar under the page, then show each caption's strip of the stacked image during its cue."""
    texts = list(dict.fromkeys((text, problem) for _, _, text, problem in caption_cues))
    parts = [f"[0:v]scale={width}:{height},pad={width}:{height + CAPTION_HEIGHT}:0:0:black[v0]"]
    parts.append(f"[1:v]split={len(caption_cues)}" + "".join(f"[s{index}]" for index in range(len(caption_cues))))
    for index, (start, end, text, problem) in enumerate(caption_cues):
        row = texts.index((text, problem))
        parts.append(f"[s{index}]crop={width}:{CAPTION_HEIGHT}:0:{row * CAPTION_HEIGHT}[c{index}]")
        parts.append(f"[v{index}][c{index}]overlay=0:{height}:enable='between(t,{start:.2f},{end:.2f})'[v{index + 1}]")
    return texts, ";".join(parts), f"[v{len(caption_cues)}]"


def ass_time(seconds):
    centiseconds = round(seconds * 100)
    return f"{centiseconds // 360000}:{centiseconds // 6000 % 60:02d}:{centiseconds // 100 % 60:02d}.{centiseconds % 100:02d}"


def subtitles(caption_cues, width, height):
    """An ASS subtitle file sized to the padded frame, drawing each cue centered in the bar under the page."""
    margin = (CAPTION_HEIGHT - FONT_SIZE) // 2
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height + CAPTION_HEIGHT}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Caption,Arial,{FONT_SIZE},&H00FFFFFF,&H00000000,0,1,0,0,2,24,24,{margin}",
        f"Style: Problem,Arial,{FONT_SIZE},&H006060FF,&H00000000,1,1,0,0,2,24,24,{margin}",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Text",
    ]
    for start, end, text, problem in caption_cues:
        clean = text.replace("\n", " ").replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: {1 if problem else 0},{ass_time(start)},{ass_time(end)},{'Problem' if problem else 'Caption'},{clean}")
    return "\n".join(lines) + "\n"


def run_ffmpeg(ffmpeg, arguments, scratch):
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *arguments], capture_output=True, text=True, cwd=scratch)
    if result.returncode != 0:
        raise ClipError(f"ffmpeg failed: {result.stderr.strip()}")


def recorded_video(record, evidence_path):
    """Resolve a run's video from evidence/, two levels above its record."""
    video = evidence_path.resolve().parent.parent / record["recording"]["video"]
    if not video.is_file():
        raise ClipError(f"the evidence names {video}, which is not here")
    return video.resolve()


def cut(evidence_path, spec, captions=True):
    """Cut the steps spec names into an MP4 in the run's folder, captioned by a browser or ffmpeg unless captions is False.

    Returns the MP4's path.
    """
    record = load(evidence_path)
    video = recorded_video(record, evidence_path)
    first, last, start, end = step_window(steps(record), spec)
    ffmpeg = require_tool("ffmpeg", "FFMPEG")
    target = evidence_path.with_suffix("") / clip_name(record, steps(record), first, last)
    target.parent.mkdir(parents=True, exist_ok=True)
    window = ["-ss", f"{start:.2f}", "-i", str(video)] + (["-t", f"{end - start:.2f}"] if end is not None else [])
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch, "clip.mp4")
        caption_cues = cues(record, start, end) if captions else []
        browser = find_browser() if caption_cues else None
        if not caption_cues:
            run_ffmpeg(ffmpeg, [*window, "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", *ENCODE, str(output)], scratch)
        elif browser:
            width, height = video_size(require_tool("ffprobe", "FFPROBE"), video)
            texts, graph, label = overlay_filter(caption_cues, width, height)
            image = render_captions(browser, texts, width, scratch)
            run_ffmpeg(ffmpeg, [*window, "-i", str(image), "-filter_complex", graph, "-map", label, *ENCODE, str(output)], scratch)
        elif can_caption_with_ffmpeg(ffmpeg):
            width, height = video_size(require_tool("ffprobe", "FFPROBE"), video)
            Path(scratch, "captions.ass").write_text(subtitles(caption_cues, width, height))
            # The filter reads the file relative to ffmpeg's working directory, which avoids escaping its path.
            graph = f"scale={width}:{height},pad=iw:ih+{CAPTION_HEIGHT}:0:0:black,subtitles=captions.ass"
            run_ffmpeg(ffmpeg, [*window, "-vf", graph, *ENCODE, str(output)], scratch)
        else:
            raise ClipError(f"nothing here can draw captions: no headless browser, and {ffmpeg} has no subtitles filter. {NO_CAPTIONS_HINT}")
        shutil.move(str(output), target)
    write_recordings(evidence_path)
    return target


def write_recordings(evidence_path):
    """Rewrite the harness's recordings.html with replay.py, which every harness keeps beside this script.

    Loaded by path, because python -I leaves the script's own folder off the import path.
    """
    spec = util.spec_from_file_location("harness_replay", Path(__file__).with_name("replay.py"))
    replay = util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    replay.write_recordings(replay.harness_of(evidence_path))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "step"


def clip_name(record, run_steps, first, last):
    """Build a shareable MP4 name from the check, steps, first label, and start time."""
    label = re.sub(r"^\s*step\s*\d+\s*[:.)-]?\s*", "", run_steps[first - 1]["label"], flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", str(record.get("started_at") or ""))
    parts = [
        slug(str(record["check"])) if record.get("check") else "",
        f"step-{first}" if first == last else f"steps-{first}-to-{last}",
        slug(label) if label.strip() else "",
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
            at = step["at"] - offset(record)
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
    platform = platform or sys.platform
    commands = INSTALL[name]
    return next((command for prefix, command in commands.items() if platform.startswith(prefix)), commands["linux"])


def capabilities():
    """What this machine can make from a recording: (lines to print, whether everything is available)."""
    ffmpeg = find_tool("ffmpeg", "FFMPEG")
    ffprobe = find_tool("ffprobe", "FFPROBE")
    browser = find_browser()
    lines = []
    if ffmpeg and ffprobe:
        lines.append(f"Stills and clips: yes, with {ffmpeg}")
    else:
        missing = " and ".join(name for name, found in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not found)
        lines.append(f"Stills and clips: no, {missing} not found. Install: {install_hint('ffmpeg')}")
    if browser:
        lines.append(f"Captions: yes, drawn by {browser}")
    elif ffmpeg and can_caption_with_ffmpeg(ffmpeg):
        lines.append(f"Captions: yes, drawn by {ffmpeg}'s subtitles filter")
    else:
        lines.append(f"Captions: no headless browser found, so clips need --no-captions. Install: {install_hint('browser')}, or set CHROME")
    lines.append("Replay pages, snapshots, and logs need none of these.")
    return lines, bool(ffmpeg and ffprobe and (browser or can_caption_with_ffmpeg(ffmpeg)))


def main():
    """Report media capabilities or list, cut, or extract a recorded run's steps."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, nargs="?", help="the run's evidence file, such as evidence/checkout-pay/2026-10-03T14-02-11Z.json")
    parser.add_argument("--check", action="store_true", help="say what this machine can make, and how to install what's missing")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--steps", help="a step number or range to cut into an MP4, such as 2-3")
    action.add_argument("--frames", metavar="STEP|failed", help="write stills across one step, or around each failed step")
    parser.add_argument("--no-captions", action="store_true", help="cut the MP4 without the caption bar")
    args = parser.parse_args()
    if args.check:
        lines, complete = capabilities()
        print("\n".join(lines))
        return 0 if complete else 1
    if args.evidence is None:
        parser.error("give an evidence file, or --check")
    try:
        if args.frames:
            for path, seconds, label in frames(args.evidence, args.frames):
                print(f"{path}  {seconds:.1f}s  {label}")
        elif args.steps:
            print(cut(args.evidence, args.steps, captions=not args.no_captions))
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
