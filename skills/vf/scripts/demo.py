#!/usr/bin/env python3
"""Make a video for people from a demo run: real speed, no cuts inside the steps it shows.

Usage:
  demo.py --check                              say whether this machine can make demo videos
  demo.py DEMO_RECORD                          list the run's steps with their captions and screens, and any
                                               ordinary passing run of a behavior it shows
  demo.py DEMO_RECORD --steps 3-6 [--max-mb N] make the MP4 of steps 3 through 6, and a still at each caption
                                               and screen switch in it

A demo run is a run `vf.py run --demo` accepted, saved under
evidence/demos/<check>/<time>.json. Its check paced itself while it ran, as
rules.md's "Demo runs" section says, and drew its own captions, screen badges,
and switch cards into the page, so this script draws nothing. It reads only
that record, the evidence records beside it, and the videos it names.

The video starts just before the first chosen step's mark and ends at the next
step mark after the last one, or at the end of the recording. Nothing between
is removed, sped up, or slowed down: every second of the MP4 is a second of
the run. A run that recorded one video per screen, each `recording` naming its
`screen`, shows at each moment the screen the latest `screen` mark named,
taken from that screen's video at the same moment, so a switch moves to the
other person's screen without skipping time. Every step mark in the range must
carry a `caption`, the wording people read; a step without one stops the
video, naming the step, so check wording never reaches an audience.

The MP4 keeps the recording's own size, in H.264 at CRF 20, which GitHub, chat
tools, and browsers play inline. When it is over --max-mb (default 10, the
smallest GitHub upload limit; paid GitHub plans allow 100), it is encoded
again at CRF 22, 24, and 26, then split at step marks into parts named
"part-1-of-2" and so on. No part is cut inside a step; a single step over the
limit stops with its size. Each part's length is checked against the steps it
covers, to within a second, which proves nothing was cut.

Stills land in the run folder's frames/, one a second after each caption and
each screen switch, plus the first and last frame, printed with the caption
and screen each should show, for an agent to read before anyone sees the
video.

The video is not proof, and it needs none: a demo can show a feature before
any check covers it. The listing names, for each behavior the demo says it
shows, the latest ordinary passing run on the same code when there is one, so
a reader who wants proof knows where to look.

Needs ffmpeg with libx264, and ffprobe, from PATH or the FFMPEG and FFPROBE
variables.

Exits 0 when the listing or the video is written, or --check finds everything;
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

DEMOS = "demos"
ACCEPTED_BY = "vf.py run"
# Starts the video just before the first step's mark, so its first frame is not mid-action.
LEAD_SECONDS = 0.5
# A still is read this long after the caption or switch it checks, once the page has drawn it.
STILL_AFTER_SECONDS = 1.0
# Each part's length may differ from the steps it covers by this much, from frame rounding, and no more.
LENGTH_TOLERANCE = 1.0
DEFAULT_MAX_MB = 10
QUALITIES = ("20", "22", "24", "26")
FRAME_RATE = "25"


class DemoError(Exception):
    pass


def objects(items):
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def evidence_dir_of(path):
    """evidence/ for a record at evidence/demos/<check>/<time>.json."""
    return path.resolve().parent.parent.parent


def load(path):
    """The demo record, with its recordings as a list; DemoError when it is not a demo run with a recording."""
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise DemoError(f"cannot read {path}: {error}") from error
    if not isinstance(record, dict) or record.get("demo") is not True:
        raise DemoError(f"{path} is not a demo run; record one with `vf.py run --demo --user-approved -- <command>`")
    if path.resolve().parent.parent.name != DEMOS:
        raise DemoError(f"{path} is not under evidence/{DEMOS}/<check>/, where vf.py run saves demo runs")
    if record.get("accepted_by") != ACCEPTED_BY:
        raise DemoError(f"{path} was not accepted by vf.py run")
    recordings = objects(record.get("recordings")) or objects([record.get("recording")])
    if not recordings or not all(isinstance(item.get("video"), str) and item["video"] for item in recordings):
        raise DemoError(f"{path} names no recording")
    for item in recordings:
        if Path(item["video"]).is_absolute() or ".." in Path(item["video"]).parts:
            raise DemoError(f"{path} names its recording {item['video']!r}, which is not a path inside evidence/")
    return dict(record, marks=objects(record.get("marks")), steps=objects(record.get("steps")), recordings=recordings)


def step_marks(record):
    """The run's step marks in time order, numbered from 1."""
    marks = sorted((mark for mark in record["marks"] if mark.get("kind") == "step" and is_seconds(mark.get("at"))),
                   key=lambda mark: mark["at"])
    return [dict(mark, number=index) for index, mark in enumerate(marks, 1)]


def is_seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def code_identity(source):
    return (source.get("commit"), source.get("dirty_hash")) if isinstance(source, dict) else (None, None)


def proof(record, evidence_dir):
    """For each behavior the demo shows: (sub-feature, evidence path from the harness or None, why it is not proven or None).

    The proving run is the latest accepted ordinary run covering the behavior. It proves the demo only when it passed,
    on the same code as the demo for every repo it records, with every harness file both runs read unchanged."""
    latest = {}
    for path in sorted(evidence_dir.glob("*/*.json")):
        try:
            other = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (not isinstance(other, dict) or other.get("accepted_by") != ACCEPTED_BY or other.get("planned_break")
                or not isinstance(other.get("sub_features"), list)):
            continue
        for sub_id in other["sub_features"]:
            if isinstance(sub_id, str) and (sub_id not in latest or str(other.get("finished_at") or "") > str(latest[sub_id][1].get("finished_at") or "")):
                latest[sub_id] = (path, other)
    found = []
    demo_code = record.get("code") if isinstance(record.get("code"), dict) else {}
    demo_harness = record.get("harness_code") if isinstance(record.get("harness_code"), dict) else {}
    for sub_id in record.get("sub_features") or []:
        if sub_id not in latest:
            found.append((sub_id, None, "no ordinary run covers it yet"))
            continue
        path, other = latest[sub_id]
        shown = path.relative_to(evidence_dir.parent).as_posix()
        code = other.get("code") if isinstance(other.get("code"), dict) else {}
        harness = other.get("harness_code") if isinstance(other.get("harness_code"), dict) else {}
        if other.get("passed") is not True:
            found.append((sub_id, shown, "its latest ordinary run did not pass"))
        elif not code or any(code_identity(code[repo]) != code_identity(demo_code.get(repo)) for repo in code):
            found.append((sub_id, shown, "its latest ordinary pass ran on different code than the demo"))
        elif any(harness[name] != demo_harness[name] for name in harness.keys() & demo_harness.keys()):
            found.append((sub_id, shown, "a harness file changed between its latest ordinary pass and the demo"))
        else:
            found.append((sub_id, shown, None))
    return found


def step_range(record, spec):
    """(first step, last step, start, end) in seconds since the run started; end is None for the end of the recording."""
    marks = step_marks(record)
    try:
        first, _, last = spec.partition("-")
        first, last = int(first), int(last or first)
    except ValueError as error:
        raise DemoError(f"--steps takes a step number or a range such as 2-3, not {spec!r}") from error
    if not marks:
        raise DemoError("the run has no step marks to choose by")
    if not 1 <= first <= last <= len(marks):
        raise DemoError(f"--steps {spec} is outside the run's steps 1-{len(marks)}")
    uncaptioned = [f"{mark['number']} ({mark.get('label')})" for mark in marks[first - 1:last] if not caption_of(mark)]
    if uncaptioned:
        raise DemoError(f"step {', '.join(uncaptioned)} has no caption; give its mark the wording people should read")
    start = max(marks[first - 1]["at"] - LEAD_SECONDS, min(item.get("starts_at", 0) for item in record["recordings"]))
    end = marks[last]["at"] if last < len(marks) else None
    return marks[first - 1], marks[last - 1], start, end


def caption_of(mark):
    caption = mark.get("caption")
    return caption.strip() if isinstance(caption, str) and caption.strip() else None


def screens(record):
    """{screen: recording} for the run's videos. A run with one video may leave its screen unnamed."""
    recordings = record["recordings"]
    if len(recordings) == 1:
        return {recordings[0].get("screen"): recordings[0]}
    named = {}
    for item in recordings:
        screen = item.get("screen")
        if not isinstance(screen, str) or not screen or screen in named:
            raise DemoError("a run with several recordings names a different screen on each")
        named[screen] = item
    return named


def segments(record, start, end):
    """[(screen, from, to)] covering start to end with no gap, switching at each screen mark that names a recorded screen."""
    by_screen = screens(record)
    if len(by_screen) == 1:
        return [(next(iter(by_screen)), start, end)]
    switches = sorted((mark for mark in record["marks"] if isinstance(mark.get("screen"), str) and is_seconds(mark.get("at"))),
                      key=lambda mark: mark["at"])
    for mark in switches:
        if mark["screen"] not in by_screen:
            raise DemoError(f"mark {mark.get('label')!r} switches to screen {mark['screen']!r}, which has no recording")
    before = [mark for mark in switches if mark["at"] <= start]
    if not before:
        raise DemoError("no screen mark comes before the first chosen step, so its screen is unknown")
    current, cursor, found = before[-1]["screen"], start, []
    for mark in switches:
        if mark["at"] <= start or (end is not None and mark["at"] >= end):
            continue
        if mark["screen"] != current:
            found.append((current, cursor, mark["at"]))
            current, cursor = mark["screen"], mark["at"]
    found.append((current, cursor, end))
    return found


def find_tool(name, variable):
    return os.environ.get(variable) or shutil.which(name)


def require_tool(name, variable):
    found = find_tool(name, variable)
    if not found:
        raise DemoError(f"{name} is not installed; install ffmpeg or set {variable}")
    return found


def probe(ffprobe, video, entries):
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", entries, "-of", "json", str(video)],
                            capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DemoError(f"ffprobe cannot read {video}: {result.stderr.strip()}") from error


def duration(ffprobe, video):
    try:
        return float(probe(ffprobe, video, "format=duration")["format"]["duration"])
    except (KeyError, ValueError) as error:
        raise DemoError(f"ffprobe cannot read {video}'s length") from error


def size(ffprobe, video):
    try:
        stream = probe(ffprobe, video, "stream=width,height")["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (KeyError, IndexError, ValueError) as error:
        raise DemoError(f"ffprobe cannot read {video}'s size") from error


def run_ffmpeg(ffmpeg, arguments, scratch):
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *arguments],
                            capture_output=True, text=True, cwd=scratch)
    if result.returncode != 0:
        raise DemoError(f"ffmpeg failed: {result.stderr.strip()}")


def encode(ffmpeg, plan, width, height, quality, output, scratch):
    """Join the plan's spans, each (video, from, to) in seconds into that video, into one MP4 at width x height."""
    inputs, filters, labels = [], [], []
    videos = list(dict.fromkeys(video for video, _, _ in plan))
    for video in videos:
        inputs += ["-i", str(video)]
    fit = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
           f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FRAME_RATE}")
    for index, (video, begin, finish) in enumerate(plan):
        trim = f"trim=start={begin:.3f}" + (f":end={finish:.3f}" if finish is not None else "")
        filters.append(f"[{videos.index(video)}:v]{trim},setpts=PTS-STARTPTS,{fit}[s{index}]")
        labels.append(f"[s{index}]")
    filters.append(f"{''.join(labels)}concat=n={len(plan)}:v=1:a=0[out]")
    run_ffmpeg(ffmpeg, [*inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-c:v", "libx264",
                        "-preset", "slow", "-crf", quality, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                        str(output)], scratch)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "demo"


def video_name(record, first, last, part=None):
    digits = re.sub(r"\D", "", str(record.get("started_at") or ""))
    name = slug(record.get("check"))
    parts = [name, "" if name.endswith("demo") else "demo",
             f"step-{first}" if first == last else f"steps-{first}-to-{last}",
             f"part-{part[0]}-of-{part[1]}" if part else "",
             f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}-{digits[8:12]}" if len(digits) >= 12 else ""]
    return "-".join(piece for piece in parts if piece) + ".mp4"


class Maker:
    """Makes one demo's MP4s and stills from its record and videos."""

    def __init__(self, path, max_bytes):
        self.path = path
        self.record = load(path)
        self.evidence_dir = evidence_dir_of(path)
        self.max_bytes = max_bytes
        self.ffmpeg = require_tool("ffmpeg", "FFMPEG")
        self.ffprobe = require_tool("ffprobe", "FFPROBE")
        self.videos = {}
        for screen, item in screens(self.record).items():
            video = self.evidence_dir / item["video"]
            if not video.is_file():
                raise DemoError(f"the record names {video}, which is not here")
            self.videos[screen] = (video.resolve(), item.get("starts_at", 0), duration(self.ffprobe, video))
        first_video = next(iter(self.videos.values()))[0]
        self.width, self.height = size(self.ffprobe, first_video)
        self.width, self.height = self.width // 2 * 2, self.height // 2 * 2
        self.folder = path.resolve().with_suffix("")

    def recording_end(self):
        return min(starts + length for _, starts, length in self.videos.values())

    def plan(self, start, end):
        """Spans of video, in seconds into each video, that cover start to end in the run's time."""
        spans = []
        for screen, begin, finish in segments(self.record, start, end):
            video, starts, _ = self.videos[screen]
            spans.append((video, max(begin - starts, 0), (finish if finish is not None else self.recording_end()) - starts))
        return spans

    def make(self, spec):
        """Write the MP4s for the steps spec names and their stills; return [(path, seconds, bytes)] and the stills."""
        first, last, start, end = step_range(self.record, spec)
        end = end if end is not None else self.recording_end()
        marks = step_marks(self.record)
        written = []
        with tempfile.TemporaryDirectory() as scratch:
            parts = self.parts(marks[first["number"] - 1:last["number"]], start, end, scratch)
            self.folder.mkdir(parents=True, exist_ok=True)
            for index, (output, begin, finish, numbers) in enumerate(parts, 1):
                label = (index, len(parts)) if len(parts) > 1 else None
                target = self.folder / video_name(self.record, numbers[0], numbers[-1], label)
                shutil.move(str(output), target)
                written.append((target, begin, finish))
        stills = self.stills(written)
        replay.write_recordings(replay.harness_of(self.path))
        return [(path, round(finish - begin, 1), path.stat().st_size) for path, begin, finish in written], stills

    def parts(self, chosen, start, end, scratch):
        """Encode chosen steps as one MP4 under the size limit, or split them at step marks until each part fits."""
        output = Path(scratch, f"part-{chosen[0]['number']}-{chosen[-1]['number']}.mp4")
        for quality in QUALITIES:
            encode(self.ffmpeg, self.plan(start, end), self.width, self.height, quality, output, scratch)
            if output.stat().st_size <= self.max_bytes:
                self.check_length(output, end - start)
                return [(output, start, end, [chosen[0]["number"], chosen[-1]["number"]])]
        if len(chosen) == 1:
            raise DemoError(f"step {chosen[0]['number']} alone is {output.stat().st_size / 1e6:.1f} MB at CRF {QUALITIES[-1]}, "
                            f"over the {self.max_bytes / 1e6:g} MB limit, and a demo never cuts inside a step")
        middle = len(chosen) // 2
        split = chosen[middle]["at"]
        return self.parts(chosen[:middle], start, split, scratch) + self.parts(chosen[middle:], split, end, scratch)

    def check_length(self, output, expected):
        length = duration(self.ffprobe, output)
        if abs(length - expected) > LENGTH_TOLERANCE:
            raise DemoError(f"the video is {length:.1f} s but its steps cover {expected:.1f} s, so something was cut")

    def stills(self, written):
        """A still a second after each caption and screen switch in each part, plus its first and last frame."""
        folder = self.folder / "frames"
        folder.mkdir(parents=True, exist_ok=True)
        found = []
        with tempfile.TemporaryDirectory() as scratch:
            for video, begin, finish in written:
                for seconds, what in self.still_times(begin, finish):
                    target = folder / f"{video.stem}-{seconds:06.1f}s.png"
                    try:
                        run_ffmpeg(self.ffmpeg, ["-ss", f"{seconds:.2f}", "-i", str(video), "-frames:v", "1", str(target)], scratch)
                    except DemoError:
                        continue
                    if target.is_file():
                        found.append((target, seconds, what))
        return found

    def still_times(self, begin, finish):
        """(seconds into the part, what the still should show) for one part covering begin to finish in run time."""
        length = finish - begin
        times = [(0.0, "first frame")]
        screen = None
        for mark in sorted(self.record["marks"], key=lambda mark: mark.get("at", 0)):
            if not is_seconds(mark.get("at")):
                continue
            if isinstance(mark.get("screen"), str) and mark["at"] <= begin:
                screen = mark["screen"]
            if not begin <= mark["at"] < finish:
                continue
            screen = mark["screen"] if isinstance(mark.get("screen"), str) else screen
            showing = []
            if caption_of(mark):
                showing.append(f"caption {caption_of(mark)!r}")
            if isinstance(mark.get("screen"), str):
                showing.append(f"switch to {mark['screen']!r}")
            if showing:
                at = min(mark["at"] - begin + STILL_AFTER_SECONDS, max(length - 0.2, 0))
                times.append((at, ", ".join(showing) + (f" on {screen!r}" if screen and "switch" not in showing[-1] else "")))
        times.append((max(length - 0.2, 0), "last frame"))
        return times


def listing(path):
    record = load(path)
    lines = [f"Demo of {record.get('check')}, recorded {record.get('started_at')}, "
             f"{'passed' if record.get('passed') else 'did not pass'}"]
    by_screen = screens(record)
    if len(by_screen) > 1:
        lines.append("Screens: " + ", ".join(str(screen) for screen in by_screen))
    for mark in step_marks(record):
        caption = caption_of(mark)
        lines.append(f"{mark['number']:>3}  {mark['at']:7.1f}s  {mark.get('label')}"
                     + (f"\n           caption: {caption}" if caption else "\n           no caption: this step cannot be shown"))
    found = [(sub_id, cited) for sub_id, cited, reason in proof(record, evidence_dir_of(path)) if not reason]
    if found:
        lines.append("Ordinary passing runs on the same code:")
        lines += [f"  {sub_id}: {cited}" for sub_id, cited in found]
    return lines


def capabilities():
    ffmpeg, ffprobe = find_tool("ffmpeg", "FFMPEG"), find_tool("ffprobe", "FFPROBE")
    if not (ffmpeg and ffprobe):
        missing = " and ".join(name for name, present in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not present)
        return [f"Demo videos: no, {missing} not found. Install ffmpeg (on macOS: brew install ffmpeg)."], False
    encoders = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "libx264" not in encoders:
        return [f"Demo videos: no, {ffmpeg} has no libx264 encoder. Install an ffmpeg build with it."], False
    return [f"Demo videos: yes, with {ffmpeg}"], True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", type=Path, nargs="?", help="a demo run's record, such as evidence/demos/checkout-pay/2026-10-03T14-02-11Z.json")
    parser.add_argument("--check", action="store_true", help="say whether this machine can make demo videos")
    parser.add_argument("--steps", help="the step number or range to show, such as 3-6")
    parser.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB,
                        help=f"the largest file the video may be, in MB (default {DEFAULT_MAX_MB}, GitHub's free-plan limit; paid plans allow 100)")
    args = parser.parse_args()
    if args.check:
        lines, complete = capabilities()
        print("\n".join(lines))
        return 0 if complete else 1
    if args.record is None:
        parser.error("give a demo run's record, or --check")
    try:
        if not args.steps:
            print("\n".join(listing(args.record)))
            return 0
        maker = Maker(args.record, int(args.max_mb * 1_000_000))
        videos, stills = maker.make(args.steps)
    except (DemoError, OSError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    for path, seconds, size_bytes in videos:
        print(f"{path}  {seconds:.1f}s  {size_bytes / 1e6:.1f} MB  {maker.width}x{maker.height}")
    print("Stills to read before handing it over:")
    for path, seconds, what in stills:
        print(f"  {path}  {seconds:.1f}s  {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
