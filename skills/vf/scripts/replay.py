#!/usr/bin/env python3
"""Write a replay page for one check run: what went wrong first, then the run's video with captions and its timeline.

Usage: replay.py EVIDENCE_FILE [--out PAGE]
       replay.py --recordings [HARNESS_DIR]

Reads evidence files at evidence/<check>/<run>.json, in the format rules.md
defines. The page goes in the run's folder beside the evidence file (the
folder named like the file), as replay.html, unless --out names another path.
It opens on each failed step with a button that plays the moment it was
decided, captions each step and action under the video rather than over the
page being recorded, and lists the whole timeline. A run with no recording gets the same page without the
video. The page loads nothing from the network. A replay shows what happened;
the steps decide the verdict.

When the evidence sits in a harness, a folder holding rules.md, each run also
rewrites the harness's recordings.html, the page a person opens to see how the
checks are doing. It gives each check one line for its latest run, naming its
first problem, and opens the rest on request: every failure, the behaviors the
run judged, its code, and earlier runs. Planned breaks are left out, since they fail on purpose. It builds the
replay page of any run that lacks one or whose page predates this script's
page format, since a run's evidence never changes. A search box narrows it to
checks matching every typed word. --recordings writes that page alone, for the
harness this script sits in unless HARNESS_DIR names another: setup runs it so
the page exists before any run does. A browser can't list a folder's files
from a page opened on disk, so every check run rewrites the page.

Exits 0 when the pages are written, 2 when the evidence cannot be read or
--recordings names a folder that is not a harness.
"""

import argparse
import html
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Starts playback a little before a failed step's verdict, so the action that led to it is on screen.
LEAD_SECONDS = 3
# The replay page's format. Bump it whenever a change to page() gives new pages something old
# ones lack; the recordings page then rebuilds every older replay page from its evidence.
REPLAY_FORMAT = 5
REPLAY_FORMAT_TAG = re.compile(r'<meta name="replay-format" content="(\d+)">')
# Earlier runs a check's details list; older ones stay in its evidence folder.
HISTORY_RUNS = 10
# Run results in the order the recordings page lists checks, so the ones that need a look come first.
STATUS_ORDER = ("Failed", "Didn't finish", "No verdict", "Passed")
RESULT_KEYS = {"Failed": "failed", "Didn't finish": "stopped", "No verdict": "other", "Passed": "passed"}


SUB_FEATURE_LINE = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (\S.*)$")


class ReplayError(Exception):
    pass


def inside_evidence(video):
    """Whether a recording path stays inside evidence/, as rules.md requires and validate.py enforces."""
    return isinstance(video, str) and not Path(video).is_absolute() and ".." not in Path(video).parts


def objects(items):
    """The objects in an evidence list; anything else in it is skipped, as a malformed mark or step."""
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load(path):
    """The evidence file as a record both pages can render: marks and steps reduced to objects, and code keyed by repo.
    ReplayError when the file is not an evidence file or names a recording outside evidence/."""
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError(f"cannot read {path}: {error}") from error
    if not isinstance(record, dict) or not isinstance(record.get("steps"), list):
        raise ReplayError(f"{path} is not an evidence file: it needs a 'steps' list")
    recording = record.get("recording")
    if isinstance(recording, dict) and recording.get("video") and not inside_evidence(recording["video"]):
        raise ReplayError(f"{path} names its recording {recording['video']!r}, which is not a path inside evidence/")
    code = record.get("code") or {}
    if not isinstance(code, dict):
        raise ReplayError(f"{path} has invalid code metadata: expected an object keyed by repo")
    return dict(record, marks=objects(record.get("marks")), steps=objects(record.get("steps")),
                code={name: source if isinstance(source, dict) else {} for name, source in code.items()})


def run_folder(evidence_path):
    """The run's folder beside its evidence file, named like the file without .json."""
    return evidence_path.with_suffix("")


def evidence_root(evidence_path):
    """The evidence/ directory of an evidence/<check>/<run>.json path."""
    return evidence_path.resolve().parent.parent


def harness_of(evidence_path):
    """The harness an evidence file sits in: the folder holding its evidence/ directory."""
    return evidence_root(evidence_path).parent


def video_path(record, evidence_path):
    """Where the run's recording should be on disk, or None when the run kept none."""
    recording = record.get("recording")
    if not isinstance(recording, dict) or not recording.get("video"):
        return None
    return evidence_root(evidence_path) / recording["video"]


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
    """The run's result as (status, one-sentence summary), from its stopped and passed fields."""
    if record.get("stopped"):
        return "Didn't finish", f"It stopped before it could decide: {record['stopped']}"
    passed = record.get("passed")
    if passed is True:
        return "Passed", "Every step passed."
    if passed is False:
        return "Failed", "A step failed."
    return "No verdict", "The run observed but decided nothing."


def versions(record):
    """Each repo's branch and short commit, such as "app main a1b2c3d (uncommitted changes)"."""
    described = []
    for name, source in (record.get("code") or {}).items():
        branch = f"{source['branch']} " if source.get("branch") else ""
        dirty = " (uncommitted changes)" if source.get("dirty") else ""
        described.append(f"{name} {branch}{str(source.get('commit', '?'))[:7]}{dirty}")
    return ", ".join(described)


def started(record):
    """When the run started, as a person reads it: "2026-10-03 14:02 UTC"."""
    value = str(record.get("started_at") or "")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


# The replay page's styles and script. Plain strings, not f-strings, so CSS and JavaScript braces stay single.
REPLAY_STYLE = """
:root {
  color-scheme: light dark;
  --text: #1d1d1f; --muted: #6e6e73; --line: #e5e5ea; --card: #fff; --page: #f5f5f7; --hover: #f0f0f3;
  --accent: #0a66c2; --now: #fff4cc; --selected: #e6f0fb;
  --pass: #1b6e3a; --fail: #b3261e; --fail-bg: #fbe7e5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --text: #f5f5f7; --muted: #a1a1a6; --line: #38383d; --card: #1c1c1e; --page: #111113; --hover: #26262a;
    --accent: #4c9cf0; --now: #3a3214; --selected: #1d2b3d;
    --pass: #6fd08c; --fail: #ff8a80; --fail-bg: #3f1a17;
  }
}
* { box-sizing: border-box; }
body { font: 15px/1.45 system-ui, -apple-system, sans-serif; margin: 0; background: var(--page); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
header { padding: 14px 20px 10px; border-bottom: 1px solid var(--line); background: var(--card); }
header a { color: var(--accent); font-size: 13px; }
h1 { font-size: 20px; margin: 4px 0 2px; }
.meta { color: var(--muted); font-size: 13px; margin: 0; }
.status { font-weight: 600; }
.status.failed, .status.stopped { color: var(--fail); }
.status.passed { color: var(--pass); }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 400px; flex: 1; min-height: 0; }
.player { overflow: auto; padding: 16px 20px 32px; }
.stage { position: sticky; top: -16px; background: var(--page); padding-top: 16px; margin-top: -16px; z-index: 1; }
video { width: 100%; max-height: 52vh; object-fit: contain; background: #000; display: block; border-radius: 8px 8px 0 0; }
.caption { background: #1d1d1f; color: #fff; padding: 8px 12px; min-height: 38px; font-size: 14px; }
.caption.problem { background: #b3261e; }
.track { position: relative; height: 26px; background: var(--card); border: 1px solid var(--line); border-top: 0; border-radius: 0 0 8px 8px; }
.track .head { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); }
.track button { position: absolute; top: 3px; transform: translateX(-50%); width: 18px; height: 18px; padding: 0; border: 0; border-radius: 50%; background: var(--fail); color: #fff; font-size: 11px; line-height: 18px; cursor: pointer; }
.track button.selected { outline: 2px solid var(--accent); outline-offset: 1px; }
.hint { color: var(--muted); font-size: 12px; margin: 6px 0 0; }
kbd { font: 11px ui-monospace, monospace; border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 4px; padding: 0 4px; background: var(--card); }
.detail { margin-top: 16px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.detail.fail { border-color: var(--fail); background: var(--fail-bg); }
.detail h2 { font-size: 16px; margin: 0 0 6px; }
.detail .result { font-weight: 600; margin: 0 0 6px; }
.detail .result.fail { color: var(--fail); } .detail .result.pass { color: var(--pass); }
.detail pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 13px/1.4 ui-monospace, monospace; margin: 8px 0; }
.detail img { display: block; max-width: 100%; margin: 10px 0; border: 1px solid var(--line); border-radius: 6px; }
.detail a, .note a { color: var(--accent); }
.detail ul { margin: 6px 0 0; padding-left: 0; list-style: none; }
.note { color: var(--muted); }
aside { border-left: 1px solid var(--line); background: var(--card); display: flex; flex-direction: column; min-height: 0; }
.summary { padding: 12px 16px; border-bottom: 1px solid var(--line); font-weight: 600; }
.summary .fail { color: var(--fail); }
#steps { overflow: auto; flex: 1; margin: 0; padding: 6px 0 24px; list-style: none; }
.group > .title { display: flex; gap: 8px; align-items: baseline; width: 100%; padding: 8px 16px; border: 0; background: none; color: inherit; font: inherit; font-weight: 600; text-align: left; cursor: pointer; }
.group > .title:hover, .row:hover { background: var(--hover); }
.group > .title .chevron { color: var(--muted); font-size: 11px; width: 10px; flex: none; }
.group > .title .label { flex: 1; min-width: 0; }
.group > .title .count { color: var(--muted); font-weight: 400; font-size: 13px; white-space: nowrap; }
.group.failed > .title .count { color: var(--fail); }
.group ul { margin: 0; padding: 0 0 4px; list-style: none; }
.row { display: flex; gap: 8px; align-items: baseline; padding: 4px 16px 4px 34px; cursor: pointer; font-size: 14px; }
.row .icon { flex: none; width: 14px; text-align: center; font-weight: 700; }
.row.pass .icon { color: var(--pass); } .row.fail .icon { color: var(--fail); } .row.action .icon { color: var(--muted); }
.row.fail { font-weight: 600; }
.row.action { color: var(--muted); }
.row .label { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.time { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; font-weight: 400; }
.now { background: var(--now); }
.selected, .selected:hover { background: var(--selected); box-shadow: inset 3px 0 0 var(--accent); }
[hidden] { display: none !important; }
@media (max-width: 860px) {
  body { display: block; height: auto; }
  .layout { display: block; }
  .player { overflow: visible; }
  aside { border-left: 0; border-top: 1px solid var(--line); }
  #steps { overflow: visible; }
}
"""

REPLAY_SCRIPT = """
const data = JSON.parse(document.getElementById('data').textContent);
const video = document.getElementById('video');
const caption = document.getElementById('caption');
const track = document.getElementById('track');
const detail = document.getElementById('detail');
const list = document.getElementById('steps');
const entries = data.timeline;
const failed = entries.filter((entry) => entry.kind === 'fail');
const clock = (seconds) => seconds === null ? '' : `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
const text = (tag, value, className) => { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; };
const details = (entry) => [entry.detail, entry.evidence ? JSON.stringify(entry.evidence, null, 2) : ''].filter(Boolean).join('\\n');
// A failure plays from a few seconds before its verdict, so the action that led to it is on screen.
const playFrom = (entry) => entry.kind === 'fail' ? Math.max(entry.video_at - data.lead, 0) : entry.video_at;
const seek = (seconds) => {
  if (!video || seconds === null) return;
  const go = () => { video.currentTime = Math.max(seconds, 0); };
  if (video.readyState >= 1) go(); else video.addEventListener('loadedmetadata', go, { once: true });
};

// Each step mark starts a group holding the checks and actions after it, so a long run reads as a few parts.
const groups = [];
for (const entry of entries) {
  if (entry.kind === 'step' || !groups.length) groups.push({ head: entry.kind === 'step' ? entry : null, entries: [] });
  // A recorder often marks the step's own action with the step's words; the group's title already says it.
  const group = groups[groups.length - 1];
  if (entry.kind !== 'step' && !(entry.kind === 'action' && group.head && entry.label === group.head.label)) group.entries.push(entry);
}
const rows = new Map();
const heads = new Map();
const expand = (group, open) => {
  group.open = open;
  group.list.hidden = !open;
  group.chevron.textContent = open ? '▾' : '▸';
  group.button.setAttribute('aria-expanded', String(open));
};
for (const group of groups) {
  const fails = group.entries.filter((entry) => entry.kind === 'fail').length;
  const checks = group.entries.filter((entry) => entry.kind !== 'action').length;
  const item = text('li', '', fails ? 'group failed' : 'group');
  group.button = text('button', '', 'title');
  group.button.type = 'button';
  group.chevron = text('span', '', 'chevron');
  group.button.appendChild(group.chevron);
  group.button.appendChild(text('span', group.head ? group.head.label : 'Before the first step', 'label'));
  group.button.appendChild(text('span', fails ? `✕ ${fails} of ${checks}` : checks ? `✓ ${checks}` : '', 'count'));
  item.appendChild(group.button);
  group.list = text('ul', '');
  for (const entry of group.entries) {
    const row = text('li', '', `row ${entry.kind}`);
    row.appendChild(text('span', entry.kind === 'pass' ? '✓' : entry.kind === 'fail' ? '✕' : '·', 'icon'));
    row.appendChild(text('span', entry.label, 'label'));
    row.appendChild(text('span', clock(entry.video_at), 'time'));
    row.onclick = () => choose(entry, true);
    rows.set(entry, row);
    group.list.appendChild(row);
  }
  item.appendChild(group.list);
  if (group.head) heads.set(group.head, group.button);
  group.button.onclick = () => {
    if (group.open && group.head && selected === group.head) expand(group, false);
    else if (group.head) choose(group.head, true);
    else expand(group, !group.open);
  };
  expand(group, fails > 0);
  list.appendChild(item);
}
const groupOf = (entry) => groups.find((group) => group.head === entry || group.entries.includes(entry));

let selected = null;
const show = (entry) => {
  detail.replaceChildren();
  detail.className = `detail ${entry.kind}`;
  if (entry.kind === 'pass' || entry.kind === 'fail') detail.appendChild(text('p', entry.kind === 'fail' ? '✕ Failed' : '✓ Passed', `result ${entry.kind}`));
  detail.appendChild(text('h2', entry.label));
  if (entry.kind === 'step') {
    const inside = groupOf(entry).entries.filter((other) => other.kind !== 'action');
    const fails = inside.filter((other) => other.kind === 'fail');
    detail.appendChild(text('p', fails.length ? `${fails.length} of ${inside.length} checks here failed.` : inside.length ? `All ${inside.length} checks here passed.` : 'No checks were decided here.', 'note'));
  }
  if (details(entry)) detail.appendChild(text('pre', details(entry)));
  if (entry.snapshot && entry.snapshot.screenshot) {
    const image = document.createElement('img');
    image.src = entry.snapshot.screenshot;
    image.alt = `The page when "${entry.label}" failed`;
    detail.appendChild(image);
  }
  if (entry.snapshot && entry.snapshot.text) {
    const page = text('a', 'Page text at the failure');
    page.href = entry.snapshot.text;
    detail.appendChild(page);
  }
};
// Keeps a row in view inside the step list without scrolling the whole page.
const reveal = (node) => {
  const box = list.getBoundingClientRect();
  const spot = node.getBoundingClientRect();
  if (spot.top < box.top || spot.bottom > box.bottom) list.scrollTop += spot.top - box.top - box.height / 3;
};
const choose = (entry, play) => {
  if (selected) (rows.get(selected) || heads.get(selected)).classList.remove('selected');
  selected = entry;
  const group = groupOf(entry);
  if (!group.open) expand(group, true);
  const node = rows.get(entry) || heads.get(entry);
  node.classList.add('selected');
  reveal(node);
  markers.forEach(([marked, button]) => button.classList.toggle('selected', marked === entry));
  show(entry);
  if (video && entry.video_at !== null) {
    seek(playFrom(entry));
    if (play) video.play();
  }
};

const markers = [];
if (video) {
  // Failure marks sit on a strip under the video, placed once its length is known.
  const head = text('div', '', 'head');
  track.appendChild(head);
  const place = () => {
    if (!Number.isFinite(video.duration) || video.duration <= 0) return;
    for (const entry of failed.filter((entry) => entry.video_at !== null)) {
      const button = text('button', '✕');
      button.type = 'button';
      button.title = `${clock(entry.video_at)} ${entry.label}`;
      button.style.left = `${Math.min(entry.video_at / video.duration, 1) * 100}%`;
      button.onclick = () => choose(entry, true);
      markers.push([entry, button]);
      track.appendChild(button);
    }
  };
  if (video.readyState >= 1) place(); else video.addEventListener('loadedmetadata', place, { once: true });

  const shown = entries.filter((entry) => entry.video_at !== null);
  let current = null;
  video.addEventListener('timeupdate', () => {
    const now = video.currentTime;
    if (Number.isFinite(video.duration) && video.duration > 0) head.style.left = `${Math.min(now / video.duration, 1) * 100}%`;
    let latest = null;
    for (const entry of shown) if (entry.video_at <= now) latest = entry;
    const problem = failed.find((entry) => entry.video_at !== null && entry.video_at <= now && now < entry.video_at + 3);
    const step = shown.filter((entry) => entry.kind === 'step' && entry.video_at <= now).pop();
    caption.textContent = problem ? `Problem: ${problem.label}` : step ? step.label : '';
    caption.classList.toggle('problem', Boolean(problem));
    if (latest === current) return;
    if (current) (rows.get(current) || heads.get(current)).classList.remove('now');
    current = latest;
    if (!current) return;
    const group = groupOf(current);
    const node = group.open ? rows.get(current) || heads.get(current) : group.button;
    node.classList.add('now');
    if (!video.paused) reveal(node);
  });
}

// j or the down arrow jumps to the next failure, k or the up arrow to the previous one.
document.addEventListener('keydown', (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey || !failed.length) return;
  const forward = event.key === 'j' || event.key === 'ArrowDown';
  if (!forward && event.key !== 'k' && event.key !== 'ArrowUp') return;
  event.preventDefault();
  const at = failed.indexOf(selected);
  const next = at === -1 ? (forward ? 0 : failed.length - 1) : (at + (forward ? 1 : -1) + failed.length) % failed.length;
  choose(failed[next], true);
});

// The recordings page's Watch links open this page at #at=<seconds into the video>, a little before a failure;
// otherwise the page opens on the first failure, ready to play from just before it.
const start = location.hash ? Number(new URLSearchParams(location.hash.slice(1)).get('at')) : NaN;
const reach = start + data.lead + 0.05;
const linked = Number.isFinite(start)
  ? failed.find((entry) => entry.video_at !== null && entry.video_at >= start && entry.video_at <= reach)
    || entries.filter((entry) => entry.video_at !== null && entry.video_at <= reach).pop()
  : null;
const first = linked || failed[0] || entries[0];
if (first) choose(first, false);
if (Number.isFinite(start)) seek(start);
"""


def page(record, video_src, link=lambda path: path):
    """The replay page's HTML: the video beside a list of the run's steps, with the chosen step's evidence under the video.

    Its script reads the timeline from an embedded JSON block, so the page needs no network.
    """
    status, summary = verdict(record)
    data = {"timeline": timeline(record, link), "lead": LEAD_SECONDS}
    # Keeps a step's text from closing the script element that carries the data.
    payload = json.dumps(data).replace("</", "<\\/")
    title = html.escape(str(record.get("check", "check run")))
    checks = [step for step in record.get("steps") or [] if isinstance(step, dict)]
    fails = sum(1 for step in checks if step.get("passed") is False)
    tally = (
        f'<span class="fail">✕ {fails} of {counted(len(checks), "step")} failed</span>' if fails
        else f"✓ All {counted(len(checks), 'step')} passed" if checks else "No steps decided"
    )
    stage = (
        f'<div class="stage"><video id="video" controls preload="metadata" src="{html.escape(video_src)}"></video>'
        '<div id="caption" class="caption"></div><div id="track" class="track" aria-label="Failures in the video"></div></div>'
        '<p class="hint">Click a step to play it. <kbd>j</kbd> <kbd>k</kbd> or <kbd>↓</kbd> <kbd>↑</kbd> jump between failures. '
        f'<a href="{html.escape(video_src)}">Open the video file</a></p>'
        if video_src else '<p class="note">This run kept no recording, so its steps and evidence are all there is to replay.</p>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="replay-format" content="{REPLAY_FORMAT}">
<title>Replay: {title}</title>
<style>{REPLAY_STYLE}</style>
</head>
<body>
<header>
<a href="{html.escape(link("../recordings.html"))}">&larr; All check runs</a>
<h1>{title}</h1>
<p class="meta"><span class="status {RESULT_KEYS[status]}">{html.escape(status)}.</span> {html.escape(summary)}
{html.escape(versions(record))}{' · started ' + html.escape(started(record)) if record.get('started_at') else ''}</p>
</header>
<div class="layout">
<main class="player">
{stage}
<section id="detail" class="detail" aria-live="polite"></section>
</main>
<aside>
<div class="summary">{tally}</div>
<ol id="steps"></ol>
</aside>
</div>
<script type="application/json" id="data">{payload}</script>
<script>{REPLAY_SCRIPT}</script>
</body>
</html>
"""


def listed_runs(evidence_dir):
    """Every readable check run as (evidence path, record), newest first. Unreadable files are left to validate.py."""
    runs = []
    for path in evidence_dir.glob("*/*.json"):
        try:
            runs.append((path, load(path)))
        except ReplayError:
            continue
    return sorted(runs, key=lambda run: str(run[1].get("started_at") or ""), reverse=True)


def has_video(record):
    """Whether the run names a recording."""
    return isinstance(record.get("recording"), dict) and bool(record["recording"].get("video"))


def counted(number, noun):
    """A count with its noun, pluralized: "1 step", "3 steps"."""
    return f"{number} {noun}{'' if number == 1 else 's'}"


def clip_label(name):
    """Label a clip's button with its step range; the full filename shows on hover."""
    span = re.search(r"(?:^|-)step(s?)-(\d+)(?:-to-(\d+))?(?:-|\.mp4$)", name)
    if not span:
        return "Clip"
    return f"Clip: steps {span.group(2)}-{span.group(3)}" if span.group(3) else f"Clip: step {span.group(2)}"


def first_sentence(paragraph):
    """A paragraph's first sentence as plain text, with Markdown code marks and link targets dropped."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", paragraph).replace("`", "")
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text.strip(), maxsplit=1)[0]


def feature_metadata(harness_dir):
    """Each readable feature file as (title, what it does, {sub-feature ID: wording}, proof text), in file order.

    What it does is the first sentence of the paragraph under the title, the feature's one-line summary.
    """
    found = []
    for path in sorted((harness_dir / "features").glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        wording, proofs, section, summary = {}, [], None, []
        for line in text.splitlines():
            if line.startswith("# "):
                section = "Title"
            elif line.startswith("## "):
                section = line[3:].strip()
            elif section == "Title" and (line.strip() or summary):
                if not line.strip():
                    section = None
                else:
                    summary.append(line.strip())
            elif section == "Sub-features" and (match := SUB_FEATURE_LINE.match(line)):
                words = match.group(2).strip()
                wording[match.group(1)] = words[:1].upper() + words[1:]
            elif section == "How to prove it" and line.startswith("- "):
                proofs.append(line)
        found.append((title, first_sentence(" ".join(summary)), wording, "\n".join(proofs)))
    return found


def check_feature(check, features):
    """(Title, what it does) of the feature file whose proof lines run this check most often, or (None, "")."""
    pattern = re.compile(rf"(?<![\w-]){re.escape(check)}(?![\w-])")
    counts = [(len(pattern.findall(proofs)), index) for index, (_, _, _, proofs) in enumerate(features)]
    best = max(counts, default=(0, None))
    return features[best[1]][:2] if best[0] else (None, "")


def behavior_wording(features):
    """Each sub-feature ID the feature files define, with its plain wording."""
    return {sub_id: words for _, _, wording, _ in features for sub_id, words in wording.items()}


def behavior_results(record):
    """Each sub-feature the run covers as (ID, "failed", "passed", or "not judged"), by the steps judging it.

    Follows the Checks rule in rules.md: a step judges the sub-features it names, and in a check
    covering one sub-feature, a step naming none judges that one.
    """
    ids = [str(sub_id) for sub_id in record.get("sub_features") or []]
    verdicts = {sub_id: [] for sub_id in ids}
    for step in record["steps"]:
        named = step.get("sub_features")
        judged = [str(sub_id) for sub_id in named] if isinstance(named, list) else ids if len(ids) == 1 else []
        for sub_id in judged:
            if sub_id in verdicts and isinstance(step.get("passed"), bool):
                verdicts[sub_id].append(step["passed"])
    return [
        (sub_id, "failed" if False in found else "passed" if found else "not judged")
        for sub_id, found in verdicts.items()
    ]


def failed_steps(record):
    """The run's steps that failed, in run order."""
    return [step for step in record["steps"] if step.get("passed") is False]


def watch_moment(record, step):
    """Seconds into the video a little before a failed step's verdict, or None when the video doesn't show it."""
    entry = next(
        (entry for entry in timeline(record) if entry["kind"] == "fail" and entry["label"] == str(step.get("name", ""))),
        None,
    )
    return max(entry["video_at"] - LEAD_SECONDS, 0) if entry and entry["video_at"] is not None else None


def outcome(record):
    """Summarize a run as (status, headline, note, playback time or None), with time in video seconds.

    The headline is what a reader looks at first: the first failed step or the stop reason. The note
    says how much of the run it covers. Playback starts just before that moment.
    """
    status = verdict(record)[0]
    steps = record["steps"]
    failed = failed_steps(record)
    if status == "Passed":
        return status, f"All {counted(len(steps), 'step')} passed", "", None
    if status == "Didn't finish":
        shown = [entry for entry in timeline(record) if entry["video_at"] is not None]
        before = f"{counted(len(failed), 'step')} had failed before it stopped" if failed else "nothing had failed before it stopped"
        watch = max(shown[-1]["video_at"] - LEAD_SECONDS, 0) if shown else None
        return status, str(record.get("stopped")), f"No verdict after {counted(len(steps), 'step')}; {before}.", watch
    if failed:
        return status, str(failed[0].get("name", "")), f"{len(failed)} of {counted(len(steps), 'step')} failed", watch_moment(record, failed[0])
    return status, verdict(record)[1], "", None


def code_cells(record):
    """The run's code as a small table: one line per repo with its branch, commit, and anything unusual about it."""
    rows = []
    for name, source in (record.get("code") or {}).items():
        branch = source.get("branch")
        notes = []
        if source.get("dirty"):
            notes.append('<span class="tag warn" title="Uncommitted changes were in this checkout, so its commit alone won\'t rebuild the code that ran">local edits</span>')
        if source.get("on_main") is False:
            notes.append('<span class="tag" title="This commit isn\'t on the repo\'s main branch yet">not on main</span>')
        branch_cell = (
            f'<td class="branch" title="{html.escape(str(branch))}">{html.escape(str(branch))}</td>' if branch
            else '<td class="branch muted" title="Checked out at a commit, not on a branch">no branch</td>'
        )
        rows.append(
            f'<tr><th scope="row" title="{html.escape(str(name))}">{html.escape(str(name))}</th>'
            f'{branch_cell}'
            f'<td class="commit">{html.escape(str(source.get("commit", "?"))[:7])}</td>'
            f'<td class="notes">{"".join(notes)}</td></tr>'
        )
    if not rows:
        return '<span class="muted">No code recorded</span>'
    columns = '<colgroup><col class="repo"><col class="branch"><col class="commit"><col class="notes"></colgroup>'
    return f'<table class="code-table">{columns}{"".join(rows)}</table>'


def run_links(path, record, folder, evidence_dir):
    """A run's replay page, opened at its problem when the video shows one, and its clips, as (href, label, kind)."""
    base = f"evidence/{path.parent.name}/{folder.name}"
    status, _, _, watch_at = outcome(record)
    links = []
    if has_video(record):
        label = {"Failed": "Watch the failure", "Didn't finish": "Watch where it stopped"}.get(status, "Watch")
        links.append((f"{base}/replay.html" + (f"#at={watch_at:g}" if watch_at is not None else ""), label, "primary"))
        links += [
            (f"{base}/{clip.name}", clip.name, "clip")
            for clip in sorted(folder.glob("*.mp4")) if clip != evidence_dir / record["recording"]["video"]
        ]
    return links


def link_html(href, text, kind):
    """A run link as a button; a clip's button shows its step range and keeps the file name for hover."""
    title = f' title="{html.escape(text)}"' if kind == "clip" else ""
    return f'<a class="button {kind}" href="{html.escape(href)}"{title}>{html.escape(clip_label(text) if kind == "clip" else text)}</a>'


def time_html(record):
    """When the run started, as a time element the page's script turns into local time."""
    when = html.escape(str(record.get("started_at") or ""))
    return f'<time datetime="{when}">{html.escape(started(record))}</time>'


def details_html(check, path, record, earlier, features, evidence_dir):
    """What a reader opens a check for: every failure, the behaviors it judged, its code, and earlier runs."""
    status, headline, _, _ = outcome(record)
    folder = run_folder(path)
    base = f"evidence/{path.parent.name}/{folder.name}"
    video = has_video(record)
    parts = []
    if status == "Didn't finish":
        parts.append(
            "<h3>Why it didn't finish</h3>"
            "<p class=\"muted\">The run ended before it could decide, so it says nothing either way about the steps it didn't reach.</p>"
            f"<pre>{html.escape(headline)}</pre>"
        )
    failed = failed_steps(record)
    if failed:
        items = []
        for step in failed:
            moment = watch_moment(record, step) if video else None
            watch = f' <a href="{html.escape(base)}/replay.html#at={moment:g}">Watch</a>' if moment is not None else ""
            detail = f'<pre>{html.escape(str(step["detail"]))}</pre>' if step.get("detail") else ""
            items.append(f'<li><strong>{html.escape(str(step.get("name", "")))}</strong>{watch}{detail}</li>')
        parts.append(f'<h3>{"Failed steps" if status == "Failed" else "Failed before it stopped"}</h3><ol class="failures">{"".join(items)}</ol>')

    wording = behavior_wording(features)
    results = behavior_results(record)
    if results:
        def listed(group):
            return "".join(f'<li title="{html.escape(sub_id)}">{html.escape(wording.get(sub_id, sub_id))}</li>' for sub_id, _ in group)
        by_result = {result: [item for item in results if item[1] == result] for result in ("failed", "passed", "not judged")}
        block = "<h3>Behaviors this run judged</h3>"
        if len(by_result["not judged"]) == len(results) and record["steps"]:
            block = (
                "<h3>Behaviors this check covers</h3>"
                '<p class="muted">Its steps aren\'t tagged with the behaviors they test, so this run can\'t tell which of these passed.</p>'
                f'<details><summary>{counted(len(results), "behavior")}</summary><ul class="behaviors">{listed(results)}</ul></details>'
            )
            by_result = {"failed": [], "passed": [], "not judged": []}
        if by_result["failed"]:
            block += f'<p class="label fail">Failed</p><ul class="behaviors">{listed(by_result["failed"])}</ul>'
        for result, label in (("passed", "passed"), ("not judged", "not judged by any step that ran")):
            if by_result[result]:
                block += f'<details><summary>{counted(len(by_result[result]), "behavior")} {label}</summary><ul class="behaviors">{listed(by_result[result])}</ul></details>'
        parts.append(block)

    parts.append(f"<h3>Code</h3>{code_cells(record)}")

    if earlier:
        rows = []
        for earlier_path, earlier_record in earlier[:HISTORY_RUNS]:
            earlier_status, earlier_headline, _, _ = outcome(earlier_record)
            earlier_base = f"evidence/{earlier_path.parent.name}/{run_folder(earlier_path).name}"
            rows.append(
                f'<li><span class="dot {RESULT_KEYS[earlier_status]}" title="{html.escape(earlier_status)}"></span>'
                f'{time_html(earlier_record)} <span class="word">{html.escape(earlier_status)}</span>'
                f'<span class="muted"> {html.escape(earlier_headline)}</span> '
                f'<a href="{html.escape(earlier_base)}/replay.html">Replay</a></li>'
            )
        hidden = len(earlier) - HISTORY_RUNS
        more = f'<p class="muted">{counted(hidden, "older run")} in <code>evidence/{html.escape(check)}/</code>.</p>' if hidden > 0 else ""
        parts.append(f'<h3>Earlier runs</h3><ul class="history">{"".join(rows)}</ul>{more}')

    clips = [link for link in run_links(path, record, folder, evidence_dir) if link[2] == "clip"]
    replay_label = "Open the replay: video, timeline, and evidence" if video else "Open the run: timeline and evidence"
    parts.append(
        '<p class="open">'
        f'<a class="button secondary" href="{html.escape(base)}/replay.html">{replay_label}</a>'
        + "".join(link_html(*link) for link in clips) + "</p>"
    )
    return "".join(parts)


# The recordings page's styles and script. Plain strings, not f-strings, so CSS and JavaScript braces stay single.
RECORDINGS_STYLE = """
:root {
  color-scheme: light dark;
  --text: #1d1d1f; --muted: #6e6e73; --line: #e5e5ea; --card: #fff; --page: #f5f5f7;
  --accent: #0a66c2; --accent-text: #fff; --chip: #eef2f7;
  --pass: #1b6e3a; --pass-bg: #e3f4e8; --fail: #b3261e; --fail-bg: #fbe7e5; --other: #6e6e73; --other-bg: #ededf0;
  --warn: #8a5300; --warn-bg: #fff1d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --text: #f5f5f7; --muted: #a1a1a6; --line: #38383d; --card: #1c1c1e; --page: #111113;
    --accent: #4c9cf0; --accent-text: #0b1a2a; --chip: #2a2f38;
    --pass: #6fd08c; --pass-bg: #173822; --fail: #ff8a80; --fail-bg: #3f1a17; --other: #a1a1a6; --other-bg: #2c2c2e;
    --warn: #ffc56b; --warn-bg: #3a2a10;
  }
}
* { box-sizing: border-box; }
body { font: 15px/1.45 system-ui, -apple-system, sans-serif; margin: 0; background: var(--page); color: var(--text); }
main { max-width: 1040px; margin: 0 auto; padding: 0 20px 48px; }
.intro { padding: 28px 0 4px; }
.eyebrow { color: var(--muted); font-size: 13px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; margin: 0 0 2px; }
h1 { font-size: 24px; margin: 0 0 16px; }
.bar { position: sticky; top: 0; z-index: 2; background: var(--page); padding: 12px 0; margin-bottom: 12px; box-shadow: 0 1px 0 var(--line), 0 6px 12px -10px rgba(0,0,0,.25); }
.search { display: flex; align-items: center; gap: 12px; }
#search { flex: 1; font: inherit; padding: 9px 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); color: var(--text); }
#search:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: transparent; }
.hint, #matches { color: var(--muted); font-size: 13px; white-space: nowrap; }
kbd { font: 12px ui-monospace, monospace; border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 4px; padding: 0 5px; background: var(--card); }
.filters { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.filters button { font: inherit; font-size: 13px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--card); color: var(--text); cursor: pointer; }
.filters button span { color: var(--muted); margin-left: 4px; }
.filters button[aria-pressed="true"] { background: var(--text); border-color: var(--text); color: var(--page); }
.filters button[aria-pressed="true"] span { color: inherit; opacity: .7; }
article.check { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin: 0 0 10px; }
article.check:target { outline: 2px solid var(--accent); }
.row { display: grid; grid-template-columns: 104px 1fr auto; gap: 14px; align-items: start; padding: 14px 18px; }
.main { min-width: 0; }
h2 { font-size: 16px; margin: 0; }
.slug { font: 12px ui-monospace, monospace; color: var(--muted); font-weight: 400; margin-left: 6px; }
.purpose { margin: 2px 0 0; color: var(--muted); font-size: 14px; }
.what { margin: 2px 0 0; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.note { margin: 2px 0 0; color: var(--muted); font-size: 13px; }
.ago::before { content: " · "; }
.badge { justify-self: start; font-size: 13px; font-weight: 600; padding: 2px 10px; border-radius: 999px; background: var(--other-bg); color: var(--other); white-space: nowrap; }
.badge.passed { background: var(--pass-bg); color: var(--pass); }
.badge.failed { background: var(--fail-bg); color: var(--fail); }
.badge.stopped { background: var(--warn-bg); color: var(--warn); }
.actions { display: flex; gap: 8px; align-items: center; }
.actions .muted { font-size: 13px; white-space: nowrap; }
.button { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; text-decoration: none; padding: 5px 12px; border-radius: 8px; border: 1px solid var(--line); color: var(--text); background: var(--card); }
.button:hover { border-color: var(--accent); color: var(--accent); }
.button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
.button.primary:hover { filter: brightness(1.1); color: var(--accent-text); }
.button.secondary { color: var(--accent); }
.button.clip { font-weight: 400; }
.toggle { font: inherit; font-size: 13px; padding: 5px 10px; border: 0; background: none; color: var(--accent); cursor: pointer; white-space: nowrap; }
.toggle::after { content: " ▸"; }
.toggle[aria-expanded="true"]::after { content: " ▾"; }
.details { border-top: 1px solid var(--line); padding: 4px 18px 16px 136px; font-size: 14px; }
.details h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 14px 0 6px; }
.details pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.4 ui-monospace, monospace; background: var(--chip); padding: 6px 8px; border-radius: 6px; margin: 4px 0 0; }
.details details { margin: 4px 0; }
.details summary { cursor: pointer; }
ol.failures { margin: 0; padding-left: 20px; }
ol.failures li { margin: 0 0 8px; }
ol.failures strong { color: var(--fail); }
ul.behaviors { margin: 2px 0 6px; padding-left: 20px; }
.label { margin: 0; font-weight: 600; }
.label.fail { color: var(--fail); }
ul.history { list-style: none; margin: 0; padding: 0; }
ul.history li { padding: 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
ul.history .word { margin-left: 6px; font-weight: 600; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--other); margin-right: 8px; }
.dot.passed { background: var(--pass); } .dot.failed { background: var(--fail); } .dot.stopped { background: var(--warn); }
.open { display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0 0; }
table.code-table { border-collapse: collapse; width: 100%; max-width: 640px; table-layout: fixed; font-size: 13px; }
.code-table th, .code-table td { text-align: left; padding: 1px 8px 1px 0; vertical-align: baseline; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.code-table col.repo { width: 150px; } .code-table col.commit { width: 70px; } .code-table col.notes { width: 170px; }
.code-table th { font-weight: 400; color: var(--muted); }
.code-table .branch { font-weight: 600; }
.code-table .branch.muted { font-weight: 400; }
.tag { display: inline-block; font-size: 11px; padding: 0 7px; border-radius: 999px; background: var(--chip); color: var(--muted); margin-left: 4px; }
.tag.warn { background: var(--warn-bg); color: var(--warn); }
.commit { font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--muted); }
.muted { color: var(--muted); }
.empty { background: var(--card); border: 1px dashed var(--line); border-radius: 12px; padding: 28px; text-align: center; color: var(--muted); }
.empty strong { color: var(--text); font-size: 16px; }
.footnote { color: var(--muted); font-size: 13px; margin-top: 18px; }
code { font: 13px ui-monospace, monospace; background: var(--chip); padding: 1px 5px; border-radius: 4px; }
[hidden] { display: none !important; }
@media (max-width: 760px) {
  .row { grid-template-columns: 1fr; gap: 6px; }
  .details { padding-left: 18px; }
}
"""

RECORDINGS_SCRIPT = """
const search = document.getElementById('search');
const matches = document.getElementById('matches');
const checks = [...document.querySelectorAll('article.check')];
const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
const ago = (date) => {
  const minutes = (date - Date.now()) / 60000;
  for (const [unit, size] of [['day', 1440], ['hour', 60], ['minute', 1]]) {
    if (Math.abs(minutes) >= size || unit === 'minute') return relative.format(Math.round(minutes / size), unit);
  }
};
for (const time of document.querySelectorAll('time[datetime]')) {
  const date = new Date(time.getAttribute('datetime'));
  if (isNaN(date)) continue;
  time.title = time.textContent;
  // The year shows only for a run from another year, so a date fits on one line.
  time.textContent = date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', ...(date.getFullYear() === new Date().getFullYear() ? {} : { year: 'numeric' }) });
  time.insertAdjacentHTML('afterend', `<span class="ago">${ago(date)}</span>`);
}
let result = 'all';
const filter = () => {
  const words = search.value.toLowerCase().split(/\\s+/).filter(Boolean);
  const narrowed = words.length > 0 || result !== 'all';
  let shown = 0;
  for (const check of checks) {
    check.hidden = !(words.every((word) => check.dataset.search.includes(word)) && (result === 'all' || check.dataset.result === result));
    if (!check.hidden) shown += 1;
  }
  matches.textContent = narrowed ? `${shown} of ${checks.length} checks` : '';
  document.getElementById('no-match').hidden = shown > 0 || !narrowed;
};
for (const button of document.querySelectorAll('.filters button')) {
  button.addEventListener('click', () => {
    result = button.dataset.result;
    for (const other of document.querySelectorAll('.filters button')) other.setAttribute('aria-pressed', String(other === button));
    filter();
  });
}
const open = (toggle, opened) => {
  toggle.setAttribute('aria-expanded', String(opened));
  document.getElementById(toggle.getAttribute('aria-controls')).hidden = !opened;
};
for (const toggle of document.querySelectorAll('.toggle')) {
  toggle.addEventListener('click', () => open(toggle, toggle.getAttribute('aria-expanded') !== 'true'));
}
// A link to a check opens its details.
const target = location.hash && document.getElementById(location.hash.slice(1));
if (target && target.matches('article.check')) open(target.querySelector('.toggle'), true);
if (search) {
  search.addEventListener('input', filter);
  search.addEventListener('keydown', (event) => { if (event.key === 'Escape') { search.value = ''; filter(); } });
  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && document.activeElement !== search) { event.preventDefault(); search.focus(); }
  });
}
"""


def recordings_page(harness_dir):
    """Build the runs page: one line per check for its latest run, the ones that need a look first.

    Each check shows its first problem in one line; Details opens every failure, the behaviors the
    run judged, its code, and earlier runs; the replay page holds the video and full timeline.
    Planned breaks are left out, since they fail on purpose; the feature map links each one.
    Links start from the harness directory; times show locally when JavaScript runs, otherwise in UTC.
    """
    evidence_dir = harness_dir / "evidence"
    runs_by_check = {}
    breaks = 0
    for path, record in listed_runs(evidence_dir):
        if record.get("planned_break"):
            breaks += 1
            continue
        runs_by_check.setdefault(str(record.get("check") or path.parent.name), []).append((path, record))
    # Runs arrive newest first and sorted() is stable, so within each result the most recently run check leads.
    ordered_checks = sorted(runs_by_check.items(), key=lambda section: STATUS_ORDER.index(outcome(section[1][0][1])[0]))
    features = feature_metadata(harness_dir)
    wording = behavior_wording(features)
    app = harness_dir.resolve().name.removeprefix("verify-")
    newest_code = next(iter(runs_by_check.values()))[0][1].get("code") or {} if runs_by_check else {}
    counts = {status: 0 for status in STATUS_ORDER}
    blocks = []
    for check, runs in ordered_checks:
        path, record = runs[0]
        status, headline, note, _ = outcome(record)
        counts[status] += 1
        key = RESULT_KEYS[status]
        title, purpose = check_feature(check, features)
        anchor = "check-" + re.sub(r"[^a-z0-9-]+", "-", check.lower())
        code = record.get("code") or {}
        differs = [name for name in sorted(set(code) | set(newest_code)) if code.get(name) != newest_code.get(name)]
        flag = (
            ' <span class="tag warn" title="This check last ran before the newest run, on different code in these repos. '
            f'Rerun it to know whether its result still holds.">Earlier code: {html.escape(", ".join(differs))}</span>' if differs else ""
        )
        links = run_links(path, record, run_folder(path), evidence_dir)
        actions = "".join(link_html(*link) for link in links if link[2] == "primary")
        if not links and status != "Passed":
            actions = '<span class="muted">No video kept</span>'
        lead = {"Failed": "Failed step: ", "Didn't finish": "Stopped: "}.get(status, "")
        heading = f'{html.escape(title)} <span class="slug">{html.escape(check)}</span>' if title else html.escape(check)
        searchable = " ".join([
            check, title or "", purpose, *(str(sub_id) for sub_id in record.get("sub_features") or []),
            *(wording.get(str(sub_id), "") for sub_id in record.get("sub_features") or []),
            *(str(step.get("name", "")) for step in record["steps"]),
            *(" ".join([started(run), *outcome(run)[:3], versions(run)]) for _, run in runs),
        ])
        blocks.append(
            f'<article class="check" id="{anchor}" data-result="{key}" data-search="{html.escape(searchable.lower())}">'
            f'<div class="row"><span class="badge {key}">{html.escape(status)}</span>'
            f'<div class="main"><h2>{heading}</h2>{f'<p class="purpose">{html.escape(purpose)}</p>' if purpose else ""}<p class="what">{f'<span class="muted">{lead}</span>' if lead else ""}{html.escape(headline)}</p>'
            f'<p class="note">{html.escape(note) + " · " if note else ""}{time_html(record)}{flag}</p></div>'
            f'<div class="actions">{actions}<button class="toggle" type="button" aria-expanded="false" aria-controls="{anchor}-details">Details</button></div></div>'
            f'<div class="details" id="{anchor}-details" hidden>{details_html(check, path, record, runs[1:], features, evidence_dir)}</div>'
            "</article>"
        )

    if blocks:
        body = "".join(blocks)
    else:
        body = (
            '<div class="empty"><strong>No check has run yet.</strong>'
            "<p>Each check run shows up here once vf.py run accepts it. A check that drives a screen keeps "
            "its video when it fails, or when it runs with <code>VERIFY_KEEP_RECORDING=1</code>.</p></div>"
        )
    left_out = (
        f'<p class="footnote">{counted(breaks, "run")} that broke the code on purpose, to prove a check can fail, '
        f'{"is" if breaks == 1 else "are"} left out. <a href="features/README.md">The feature map</a> links each one from the behavior it proves.</p>'
        if breaks else ""
    )
    filters = "".join(
        f'<button type="button" data-result="{RESULT_KEYS[status]}" aria-pressed="false">{html.escape(status)} <span>{counts[status]}</span></button>'
        for status in STATUS_ORDER if counts[status]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(app)} · Verification framework</title>
<style>{RECORDINGS_STYLE}</style>
</head>
<body>
<main>
<div class="intro">
<p class="eyebrow">Verification framework</p>
<h1>{html.escape(app)}</h1>
</div>
<div class="bar"{"" if blocks else " hidden"}>
<div class="search">
<input id="search" type="search" placeholder="Search by check, behavior, step, branch, or commit" aria-label="Search checks">
<span id="matches" aria-live="polite"></span>
<span class="hint"><kbd>/</kbd> to search</span>
</div>
<div class="filters" role="group" aria-label="Show checks by their latest result">
<button type="button" data-result="all" aria-pressed="true">All <span>{len(blocks)}</span></button>
{filters}
</div>
</div>
<p id="no-match" class="empty" hidden>No check matches. Try fewer words, part of a branch or step name, or the All filter.</p>
{body}
{left_out}
</main>
<script>{RECORDINGS_SCRIPT}</script>
</body>
</html>
"""


def write_atomically(target, text):
    """Write the page through a temporary file in the same folder, so a reader never opens a half-written one."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False,
    )
    try:
        with temporary:
            temporary.write(text)
        Path(temporary.name).replace(target)
    finally:
        Path(temporary.name).unlink(missing_ok=True)


def is_harness(folder):
    """Whether a folder is a verification harness, by the rules.md every harness holds."""
    return (folder / "rules.md").is_file()


def replay_is_current(page_path):
    """Whether a replay page exists and was built in this script's page format."""
    try:
        match = REPLAY_FORMAT_TAG.search(page_path.read_text())
    except OSError:
        return False
    return bool(match) and int(match.group(1)) >= REPLAY_FORMAT


def write_recordings(harness_dir):
    """Rewrite the harness's recordings.html, first building any run's replay page that is missing or in an older
    page format. Evidence stays unchanged. Returns the page's path, or None, writing nothing, outside a harness."""
    if not is_harness(harness_dir):
        return None
    for path, _ in listed_runs(harness_dir / "evidence"):
        if not replay_is_current(run_folder(path) / "replay.html"):
            write_page(path)
    target = harness_dir / "recordings.html"
    write_atomically(target, recordings_page(harness_dir))
    return target


def write_replay(evidence_path, out=None):
    """Write one run's replay page, then rewrite its harness's recordings.html.

    Returns the page's path, the video path the evidence names, and the recordings page's path or None.
    """
    target, video = write_page(evidence_path, out)
    return target, video, write_recordings(harness_of(evidence_path))


def write_page(evidence_path, out=None):
    """Write one run's replay page. Returns the page's path and the video path the evidence names."""
    record = load(evidence_path)
    target = out or run_folder(evidence_path) / "replay.html"
    video = video_path(record, evidence_path)
    def link(path):
        return Path(os.path.relpath(evidence_root(evidence_path) / path, target.resolve().parent)).as_posix()

    source = link(record["recording"]["video"]) if video else None
    write_atomically(target, page(record, source, link))
    return target, video


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, nargs="?", help="the run's evidence file, such as evidence/checkout-pay/2026-10-03T14-02-11Z.json")
    parser.add_argument("--out", type=Path, help="where to write the page (default: replay.html in the run's folder)")
    parser.add_argument(
        "--recordings", type=Path, nargs="?", const=Path(__file__).resolve().parents[2], metavar="HARNESS_DIR",
        help="write only recordings.html (default: the harness this script sits in, at scripts/framework/)",
    )
    args = parser.parse_args()
    if args.recordings is not None:
        try:
            recordings = write_recordings(args.recordings)
        except OSError as error:
            print(f"STOPPED: {error}", file=sys.stderr)
            return 2
        if recordings is None:
            print(f"STOPPED: {args.recordings} is not a harness: it has no rules.md", file=sys.stderr)
            return 2
        print(recordings.resolve())
        return 0
    if args.evidence is None:
        parser.error("give an evidence file, or --recordings")
    try:
        target, video, recordings = write_replay(args.evidence, args.out)
    except (ReplayError, OSError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    print(target)
    if recordings is None:
        print("The evidence is not inside a harness, so no recordings page was written.")
    else:
        print(f"Recorded runs: {recordings}")
    if video is not None and not video.is_file():
        print(f"WARN the evidence names {video}, which is not here; the page will show no video", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
