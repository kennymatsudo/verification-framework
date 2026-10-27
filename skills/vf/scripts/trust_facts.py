#!/usr/bin/env python3
"""Gather what a verification harness records about each behavior's check, as JSON, or as one HTML page.

Usage: trust_facts.py HARNESS_DIR [--html PATH]

Reads the harness's features/*.json, status.md, notes.md, and the evidence they cite, and
prints one JSON object:

- harness: the harness directory name.
- behaviors: one entry per sub-feature, in feature-map order:
  - id, feature, behavior: the behavior's ID, its feature's name, and its words.
  - plan: its agreed plan (what the check does and reads), or null.
  - proof: "check", "none", or "unreachable", from its entry.
  - command: the check's command, or null.
  - reads: what the entry says the check reads, such as "state", or null.
  - break: the newest planned break aimed at this behavior, or null when none is recorded:
    {"date", "what", "evidence", "on_hand", "aimed_at", "failed_steps"}. It comes from
    the accepted break runs in evidence/, or, when none is here, from the harness's
    evidence/breaks.jsonl log with on_hand false; aimed_at lists the sub-features the
    break run says it broke; failed_steps lists the steps judging this behavior that
    failed in it, empty when none did.
  - not_break_tested: the stated reason, or null.
  - unreachable: the blocker and route tried, or null.
  - result: the last Latest results line for this behavior, or null:
    {"verdict", "evidence", "on_hand", "finished_at", "reads", "code"}, where
    code maps each repo to {"commit", "dirty", "dirty_hash", "dirty_files", "on_main",
    "behind_head"}; dirty_files is the evidence's list, null when it has none;
    behind_head counts commits between the tested commit and the checkout's
    HEAD, null when the checkout or commit can't be found.
  - caveats: lines under notes.md's "Where a pass can mislead" that start with this id.
- may_mislead, untested, known_failing: the other lines of those notes.md sections.
- tally: counts across behaviors (see TALLY below).

The harness's own scripts/framework/validate.py supplies the format parser, so this reads
any harness whose validate.py matches its feature files. It judges nothing: run
validate.py for format errors and stale-evidence warnings.

--html writes a self-contained page to PATH and prints the path instead.

Exits 0 with the output, 2 when the harness has no scripts/framework/validate.py or no
features/ folder, with the reason on a STOPPED: line on stderr.
"""

import argparse
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

TALLY = {
    "behaviors": "sub-features in the map",
    "checked": "have a check",
    "caught_a_break": "check failed on a planned break whose evidence is here",
    "break_not_on_hand": "a planned break is recorded, but its evidence is not in this checkout",
    "never_broken": "check has no recorded planned break",
    "no_check": "no check yet",
    "unreachable": "the harness cannot reach it",
    "verified": "latest result Verified",
    "failed": "latest result Failed",
    "not_verified": "latest result Not verified",
    "no_result": "no latest result",
    "behind_head": "latest result ran on a commit other than the checkout's HEAD",
}


class Stopped(Exception):
    pass


def load_validator(harness_dir):
    """Load the harness's own parser so its recorded formats remain authoritative."""
    path = harness_dir / "scripts" / "framework" / "validate.py"
    if not path.is_file():
        raise Stopped(f"{path} is missing; this reads only harnesses vf built")
    spec = importlib.util.spec_from_file_location("harness_validate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    """The JSON a file holds, or None when it cannot be read or is not JSON."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def feature_files(features_dir):
    """The feature files in feature-map order: every features/<slug>.json by name; none when the folder doesn't exist yet."""
    return sorted(features_dir.glob("*.json")) if features_dir.is_dir() else []


def parse_proof(validate, harness_dir, sub_id, entry, records):
    """The proof facts for one behavior from its entry: proof kind, command, what it reads,
    its newest planned break, and any not_break_tested or unreachable reason."""
    kind = validate.behavior_kind(entry)
    facts = {"proof": "check" if kind == "command" else kind, "command": None, "reads": None,
             "break": None, "not_break_tested": None, "unreachable": None}
    if kind == "unreachable":
        facts["unreachable"] = validate.unreachable_text(entry)[len("Unreachable: "):]
    if kind != "command":
        return facts
    facts["command"] = entry.get("check")
    facts["reads"] = entry.get("reads") or None
    facts["not_break_tested"] = validate.not_break_tested_reason(entry)
    facts["break"] = break_facts(validate, harness_dir, sub_id, records)
    return facts


def break_facts(validate, harness_dir, sub_id, records):
    """The newest planned break aimed at sub_id: from an accepted run on this machine, else from evidence/breaks.jsonl."""
    aimed = validate.aimed_breaks(records, sub_id)
    if aimed:
        path, record = aimed[-1]
        return {
            "date": str(record.get("finished_at") or "")[:10],
            "what": record["planned_break"].get("what"),
            "evidence": path.relative_to(harness_dir).as_posix(),
            "on_hand": True,
            "aimed_at": record["planned_break"].get("sub_features"),
            "failed_steps": [step.get("name") for step in validate.steps_judging(record, sub_id) if step.get("passed") is False]
            if record.get("passed") is False else [],
        }
    logged = [entry for entry in break_log(harness_dir) if entry.get("sub_feature") == sub_id]
    if logged:
        entry = logged[-1]
        return {"date": str(entry.get("at") or "")[:10], "what": entry.get("what"), "evidence": entry.get("evidence"),
                "on_hand": False, "aimed_at": [sub_id], "failed_steps": []}
    return None


def break_log(harness_dir):
    """The entries vf.py break run appended to evidence/breaks.jsonl, skipping malformed lines."""
    path = harness_dir / "evidence" / "breaks.jsonl"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def code_facts(validate, record, checkouts):
    """Each repo's code as the evidence recorded it, plus how many commits behind the checkout's HEAD it is."""
    facts = {}
    for repo, source in (record.get("code") or {}).items():
        source = source or {}
        commit = source.get("commit")
        checkout = checkouts.get(repo)
        behind = validate.git(checkout, "rev-list", "--count", f"{commit}..HEAD") if checkout and commit else None
        facts[repo] = {"commit": commit, "dirty": source.get("dirty"), "dirty_hash": source.get("dirty_hash"), "dirty_files": source.get("dirty_files"),
                       "on_main": source.get("on_main"), "behind_head": int(behind) if behind is not None else None}
    return facts


def latest_results(validate, harness_dir, checkouts):
    """Each behavior's latest result from status.md, with its evidence when on hand, and notes.md's caveat lists."""
    status = harness_dir / "status.md"
    text = status.read_text() if status.is_file() else ""
    notes = harness_dir / "notes.md"
    _, body = validate.sections(notes.read_text() if notes.is_file() else "")
    results = {}
    for line in validate.latest_result_lines(text).values():
        match = validate.RESULT.match(line)
        cite = validate.EVIDENCE_CITE.search(line)
        record = read_json(harness_dir / cite.group(1)) if cite else None
        results[match.group(1)] = {
            "verdict": match.group(2),
            "evidence": cite.group(1) if cite else None,
            "on_hand": record is not None,
            "finished_at": (record or {}).get("finished_at"),
            "reads": (record or {}).get("reads"),
            "code": code_facts(validate, record, checkouts) if record else {},
        }
    bullets = {
        name: [line[2:] for line in body.get(heading, []) if line.startswith("- ")]
        for name, heading in (("may_mislead", "Where a pass can mislead"), ("untested", "Untested cases"),
                              ("known_failing", "Known failing checks"))
    }
    return results, bullets


def gather(harness_dir):
    """Everything this script prints: each mapped behavior's proof and latest result, the notes.md lists, and the tally."""
    validate = load_validator(harness_dir)
    project = validate.project_root(harness_dir)
    repos = (validate.manifest(harness_dir) or {}).get("repos") or {}
    checkouts = {name: validate.resolve_repo(locator, project) for name, locator in repos.items() if isinstance(locator, str)}
    results, bullets = latest_results(validate, harness_dir, checkouts)
    records = validate.accepted_records(harness_dir / "evidence")

    behaviors = []
    for path in feature_files(harness_dir / "features"):
        data = read_json(path) or {}
        title = str(data.get("name") or path.stem)
        for sub_id, spec in (data.get("behaviors") or {}).items():
            spec = spec if isinstance(spec, dict) else {}
            entry = {"id": sub_id, "feature": title, "behavior": str(spec.get("words", "")), "plan": spec.get("plan")}
            entry.update(parse_proof(validate, harness_dir, sub_id, spec, records))
            entry["result"] = results.get(sub_id)
            entry["caveats"] = [line[len(sub_id) + 2:] for line in bullets["may_mislead"] if line.startswith(sub_id + ": ")]
            behaviors.append(entry)

    # A caveat about one behavior is listed with that behavior; the rest stay in the general list.
    mapped_ids = {behavior["id"] for behavior in behaviors}
    bullets["may_mislead"] = [line for line in bullets["may_mislead"] if line.partition(": ")[0] not in mapped_ids]
    return {"harness": harness_dir.name, "behaviors": behaviors, **bullets, "tally": tally(behaviors)}


def tally(behaviors):
    """Counts over the behaviors for each TALLY key, reported in the JSON output and the HTML header."""
    counts = dict.fromkeys(TALLY, 0)
    counts["behaviors"] = len(behaviors)
    for behavior in behaviors:
        if behavior["proof"] == "check":
            counts["checked"] += 1
            if not behavior["break"]:
                counts["never_broken"] += 1
            elif behavior["break"]["on_hand"] and behavior["break"]["failed_steps"]:
                counts["caught_a_break"] += 1
            elif not behavior["break"]["on_hand"]:
                counts["break_not_on_hand"] += 1
        elif behavior["proof"] == "none":
            counts["no_check"] += 1
        else:
            counts["unreachable"] += 1
        result = behavior["result"]
        if not result:
            counts["no_result"] += 1
            continue
        counts[result["verdict"].lower().replace(" ", "_")] += 1
        if any(code["behind_head"] != 0 for code in result["code"].values()):
            counts["behind_head"] += 1
    return counts


def caught_cell(behavior):
    """The 'Seen catching a problem?' cell: whether the behavior's check has failed on a planned break, in plain words."""
    if behavior["proof"] == "none":
        return "No check yet"
    if behavior["proof"] == "unreachable":
        return f"Can't be checked: {behavior['unreachable']}"
    if behavior["not_break_tested"]:
        return f"Never shown failing: {behavior['not_break_tested']}"
    planned_break = behavior["break"]
    if not planned_break:
        return "Never shown failing"
    if not planned_break["on_hand"]:
        return f"Recorded {planned_break['date']}: {planned_break['what']} (proof not in this checkout)"
    if planned_break["aimed_at"] is not None and behavior["id"] not in planned_break["aimed_at"]:
        return f"Break on {planned_break['date']} was aimed at something else: {planned_break['what']}"
    if not planned_break["failed_steps"]:
        return f"Break on {planned_break['date']} did not fail a step that checks this: {planned_break['what']}"
    return f"Failed when we broke it ({planned_break['date']}): {planned_break['what']}"


def result_cell(behavior):
    """The 'Latest result' cell: the verdict, each repo's commit and how far behind HEAD it is, and the date."""
    result = behavior["result"]
    if not result:
        return "No result recorded"
    parts = [result["verdict"]]
    for repo, code in result["code"].items():
        commit = (code["commit"] or "unknown")[:7]
        behind = code["behind_head"]
        where = ("on HEAD" if behind == 0 else f"{behind} commits behind HEAD" if behind else "commit not in this checkout")
        dirty = f", uncommitted: {', '.join(code['dirty_files'])}" if code["dirty_files"] else ", uncommitted changes"
        parts.append(f"{repo} {commit}, {where}" + (dirty if code["dirty"] else ""))
    if result["finished_at"]:
        parts.append(result["finished_at"][:10])
    return ". ".join(parts)


def render_html(facts):
    """The HTML page for the gathered facts: the tally, then one row per behavior."""
    escape = html.escape
    counts = facts["tally"]
    rows = []
    for behavior in facts["behaviors"]:
        how = behavior["plan"] or behavior["reads"] or ""
        caveats = "".join(f"<li>{escape(caveat)}</li>" for caveat in behavior["caveats"])
        proof = behavior["result"]["evidence"] if behavior["result"] and behavior["result"]["evidence"] else ""
        rows.append(
            f"<tr><td><b>{escape(behavior['feature'])}</b><br>{escape(behavior['behavior'])}<br><code>{escape(behavior['id'])}</code></td>"
            f"<td>{escape(how)}{f'<ul class=warn>{caveats}</ul>' if caveats else ''}</td>"
            f"<td>{escape(caught_cell(behavior))}</td><td>{escape(result_cell(behavior))}</td><td><code>{escape(proof)}</code></td></tr>"
        )
    lists = "".join(
        f"<h2>{title}</h2><ul>{''.join(f'<li>{escape(item)}</li>' for item in facts[key])}</ul>"
        for key, title in (("known_failing", "Known failing checks"), ("may_mislead", "Where a pass can mislead"),
                           ("untested", "Untested cases"))
        if facts[key]
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>What {escape(facts['harness'])} checks</title>
<style>
body {{ font: 15px/1.45 system-ui, sans-serif; margin: 2rem; color: #1d1d1f; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #ddd; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #f5f5f7; }}
code {{ font-size: 13px; }}
.warn {{ color: #9a3412; margin: .3rem 0 0; padding-left: 1.1rem; }}
</style>
<h1>What {escape(facts['harness'])} checks</h1>
<p>{counts['behaviors']} behaviors. {counts['caught_a_break']} have a check we've seen catch a deliberate break.
{counts['never_broken'] + counts['break_not_on_hand']} have a check we haven't seen fail here. {counts['no_check'] + counts['unreachable']} have no check.</p>
<p>This page shows what the harness records. Whether a check acts like a real user, and reads the result itself
rather than asking the app, is in its code: ask your agent to explain that check.</p>
<table>
<tr><th>Behavior</th><th>How it's checked</th><th>Seen catching a problem?</th><th>Latest result</th><th>Proof</th></tr>
{''.join(rows)}
</table>
{lists}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("harness_dir", type=Path)
    parser.add_argument("--html", type=Path, metavar="PATH", help="write a self-contained page to PATH")
    args = parser.parse_args()
    try:
        facts = gather(args.harness_dir.resolve())
    except Stopped as reason:
        print(f"STOPPED: {reason}", file=sys.stderr)
        return 2
    if args.html:
        args.html.write_text(render_html(facts))
        print(args.html)
    else:
        print(json.dumps(facts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
