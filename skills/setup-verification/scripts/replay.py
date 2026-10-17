#!/usr/bin/env python3
"""Write a replay page for one check run: what went wrong first, then the run's video with captions and its timeline.

Usage: replay.py EVIDENCE_FILE [--out PAGE]

Reads only the evidence file in the format rules.md defines. The page goes in
the run's folder beside the evidence file (the folder named like the file),
as replay.html, unless --out names another path. It opens on each failed step
with a button that plays the moment it was decided, captions each step and
action under the video rather than over the page being recorded, and lists
the whole timeline. A run with no recording gets the same page without the
video. The page loads nothing from the network. A replay shows what happened;
the steps decide the verdict.

Exits 0 when the page is written, 2 when the evidence cannot be read.
"""

import argparse
import html
import json
import os
import sys
from pathlib import Path

# Starts playback a little before a failed step's verdict, so the action that led to it is on screen.
LEAD_SECONDS = 3


class ReplayError(Exception):
    pass


def inside_evidence(video):
    """Whether a recording path stays inside evidence/, as rules.md requires and check.py enforces."""
    return isinstance(video, str) and not Path(video).is_absolute() and ".." not in Path(video).parts


def objects(items):
    """The objects in an evidence list; anything else in it is skipped, as a malformed mark or step."""
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load(path):
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError(f"cannot read {path}: {error}") from error
    if not isinstance(record, dict) or not isinstance(record.get("steps", []), list):
        raise ReplayError(f"{path} is not an evidence file: it needs a 'steps' list")
    recording = record.get("recording")
    if isinstance(recording, dict) and recording.get("video") and not inside_evidence(recording["video"]):
        raise ReplayError(f"{path} names its recording {recording['video']!r}, which is not a path inside evidence/")
    return dict(record, marks=objects(record.get("marks")), steps=objects(record.get("steps")))


def run_folder(evidence_path):
    return evidence_path.with_suffix("")


def video_path(record, evidence_path):
    recording = record.get("recording")
    if not isinstance(recording, dict) or not recording.get("video"):
        return None
    return evidence_path.parent / recording["video"]


def timeline(record, link=lambda path: path):
    """Every mark and step in time order, each with its seconds into the recording, or None when not recorded.

    link turns a path from evidence/ into one the page can open.
    """
    recording = record.get("recording") if isinstance(record.get("recording"), dict) else None
    offset = recording.get("starts_at", 0) if recording else None
    entries = []
    for mark in record.get("marks") or []:
        entries.append({"at": mark.get("at"), "kind": mark.get("kind", "action"), "label": str(mark.get("label", ""))})
    for step in record.get("steps") or []:
        entries.append({
            "at": step.get("at"),
            "kind": "pass" if step.get("passed") else "fail",
            "label": str(step.get("name", "")),
            "detail": str(step.get("detail", "")),
            "evidence": step.get("evidence"),
            "snapshot": {
                kind: link(path) for kind, path in (step.get("snapshot") or {}).items()
                if kind in ("screenshot", "text") and isinstance(path, str)
            },
        })
    entries = [entry for entry in entries if isinstance(entry["at"], (int, float))]
    entries.sort(key=lambda entry: (entry["at"], entry["kind"] != "step"))
    for entry in entries:
        seconds = entry["at"] - offset if offset is not None else None
        entry["video_at"] = round(seconds, 1) if seconds is not None and seconds >= 0 else None
    return entries


def verdict(record):
    if record.get("stopped"):
        return "Stopped", f"Stopped: {record['stopped']}"
    passed = record.get("passed")
    if passed is True:
        return "Passed", "Every step passed."
    if passed is False:
        return "Failed", "A step failed."
    return "No verdict", "The run observed but decided nothing."


def page(record, video_src, link=lambda path: path):
    """The replay page's HTML. Its script reads the timeline from an embedded JSON block, so the page needs no network."""
    status, summary = verdict(record)
    code = record.get("code") or {}
    versions = ", ".join(
        f"{name} {str((source or {}).get('commit', '?'))[:7]}{' (uncommitted changes)' if (source or {}).get('dirty') else ''}"
        for name, source in code.items()
    )
    data = {"timeline": timeline(record, link), "lead": LEAD_SECONDS}
    # Keeps a step's text from closing the script element that carries the data.
    payload = json.dumps(data).replace("</", "<\\/")
    title = html.escape(str(record.get("check", "check run")))
    video = (
        f'<video id="video" controls preload="metadata" src="{html.escape(video_src)}"></video>'
        '<div id="caption" class="caption"></div>'
        if video_src else '<p class="note">This run kept no recording, so the timeline below is all there is to replay.</p>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Replay: {title}</title>
<style>
body {{ font: 15px/1.45 system-ui, sans-serif; margin: 24px auto; max-width: 1200px; padding: 0 16px; color: #1d1d1f; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
.meta {{ color: #555; margin: 0 0 16px; }}
.status {{ font-weight: 600; }}
.status.Failed, .status.Stopped {{ color: #b3261e; }}
.status.Passed {{ color: #1b6e3a; }}
video {{ width: 100%; background: #000; display: block; }}
.caption {{ background: #111; color: #fff; padding: 10px 14px; min-height: 22px; font-size: 16px; }}
.caption.problem {{ background: #b3261e; }}
.note {{ color: #555; }}
.problem-card {{ border: 1px solid #e0b4b0; background: #fdf3f2; border-radius: 6px; padding: 10px 14px; margin: 0 0 10px; }}
.problem-card img {{ display: block; max-width: 480px; margin: 8px 0; border: 1px solid #ddd; }}
.problem-card pre, li pre {{ white-space: pre-wrap; margin: 6px 0 0; font-size: 13px; }}
button {{ font: inherit; cursor: pointer; }}
ol {{ padding-left: 0; list-style: none; }}
li {{ padding: 4px 8px; border-left: 3px solid #ddd; margin: 2px 0; }}
li.step {{ border-color: #333; font-weight: 600; margin-top: 12px; }}
li.pass {{ border-color: #1b6e3a; }}
li.fail {{ border-color: #b3261e; background: #fdf3f2; }}
li.now {{ background: #fff6d6; }}
.time {{ color: #777; font-variant-numeric: tabular-nums; margin-right: 8px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta"><span class="status {html.escape(status.replace(' ', ''))}">{html.escape(status)}.</span> {html.escape(summary)}
{html.escape(versions)}{' · started ' + html.escape(str(record.get('started_at'))) if record.get('started_at') else ''}</p>
<section id="problems"></section>
{video}
<h2>Timeline</h2>
<ol id="timeline"></ol>
<script type="application/json" id="data">{payload}</script>
<script>
const data = JSON.parse(document.getElementById('data').textContent);
const video = document.getElementById('video');
const caption = document.getElementById('caption');
const entries = data.timeline;
const clock = (seconds) => seconds === null ? '' : `${{Math.floor(seconds / 60)}}:${{String(Math.floor(seconds % 60)).padStart(2, '0')}}`;
const play = (seconds) => {{ if (!video || seconds === null) return; video.currentTime = Math.max(seconds, 0); video.play(); }};
const text = (tag, value, className) => {{ const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; }};
const details = (entry) => [entry.detail, entry.evidence ? JSON.stringify(entry.evidence, null, 2) : ''].filter(Boolean).join('\\n');

const problems = document.getElementById('problems');
const failed = entries.filter((entry) => entry.kind === 'fail');
if (failed.length) problems.appendChild(text('h2', 'What went wrong'));
for (const entry of failed) {{
  const card = text('div', '', 'problem-card');
  card.appendChild(text('strong', entry.label));
  if (details(entry)) card.appendChild(text('pre', details(entry)));
  if (entry.snapshot && entry.snapshot.screenshot) {{
    const image = document.createElement('img');
    image.src = entry.snapshot.screenshot;
    image.alt = `The page when "${{entry.label}}" failed`;
    card.appendChild(image);
  }}
  if (entry.snapshot && entry.snapshot.text) {{
    const page = text('a', 'Page text at the failure');
    page.href = entry.snapshot.text;
    card.appendChild(page);
    card.appendChild(document.createTextNode(' '));
  }}
  if (video && entry.video_at !== null) {{
    const button = text('button', `Play from ${{clock(Math.max(entry.video_at - data.lead, 0))}}`);
    button.onclick = () => play(entry.video_at - data.lead);
    card.appendChild(button);
  }}
  problems.appendChild(card);
}}

const list = document.getElementById('timeline');
const items = entries.map((entry) => {{
  const item = document.createElement('li');
  item.className = entry.kind;
  item.appendChild(text('span', clock(entry.video_at), 'time'));
  const mark = entry.kind === 'pass' ? 'Passed: ' : entry.kind === 'fail' ? 'Failed: ' : '';
  item.appendChild(document.createTextNode(mark + entry.label));
  if (entry.kind === 'fail' && details(entry)) item.appendChild(text('pre', details(entry)));
  if (video && entry.video_at !== null) {{ item.style.cursor = 'pointer'; item.onclick = () => play(entry.video_at); }}
  list.appendChild(item);
  return item;
}});

if (video) {{
  const shown = entries.filter((entry) => entry.video_at !== null && entry.kind !== 'pass');
  video.addEventListener('timeupdate', () => {{
    const now = video.currentTime;
    let current = null;
    for (const entry of shown) if (entry.video_at <= now) current = entry;
    const problem = failed.find((entry) => entry.video_at !== null && entry.video_at <= now && now < entry.video_at + 3);
    caption.textContent = problem ? `Problem: ${{problem.label}}` : current ? current.label : '';
    caption.classList.toggle('problem', Boolean(problem));
    items.forEach((item, index) => item.classList.toggle('now', entries[index] === current));
  }});
}}
</script>
</body>
</html>
"""


def write_replay(evidence_path, out=None):
    """Write the replay page, replacing any earlier one whole. Returns the page's path and the video path the evidence names."""
    record = load(evidence_path)
    target = out or run_folder(evidence_path) / "replay.html"
    video = video_path(record, evidence_path)
    def link(path):
        return Path(os.path.relpath(evidence_path.parent / path, target.parent)).as_posix()

    source = link(record["recording"]["video"]) if video else None
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(page(record, source, link))
    temporary.replace(target)
    return target, video


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, help="the run's evidence file, such as evidence/checkout-pay-20261003T140211Z.json")
    parser.add_argument("--out", type=Path, help="where to write the page (default: replay.html in the run's folder)")
    args = parser.parse_args()
    try:
        target, video = write_replay(args.evidence, args.out)
    except (ReplayError, OSError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    print(target)
    if video is not None and not video.is_file():
        print(f"WARN the evidence names {video}, which is not here; the page will show no video", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
