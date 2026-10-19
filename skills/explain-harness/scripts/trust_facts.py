#!/usr/bin/env python3
"""Gather what a verification harness records about each behavior's check, as JSON, or as one HTML page.

Usage: trust_facts.py HARNESS_DIR [--html PATH]

Reads the harness's feature files, status.md, and the evidence they cite, and
prints one JSON object:

- harness: the harness directory name.
- behaviors: one entry per sub-feature, in feature-map order:
  - id, feature, behavior: the sub-feature line.
  - plan: its Verification plan line (what the check does and reads), or null.
  - proof: "check", "none", or "unreachable", from its How to prove it line.
  - command: the check's command, or null.
  - reads: what the proof line says the check reads, such as "(state)", or null.
  - break: the planned break, or null when none is recorded:
    {"date", "what", "evidence", "on_hand", "aimed_at", "failed_steps"}. on_hand
    is false when the cited file is not in this checkout; aimed_at lists the
    sub-features the break run says it broke, or null when it says none;
    failed_steps lists the steps judging this behavior that failed in it, empty
    when the break was not aimed at this behavior or none did.
  - not_break_tested: the stated reason, or null.
  - unreachable: the blocker and route tried, or null.
  - result: the last Latest results line for this behavior, or null:
    {"verdict", "evidence", "on_hand", "finished_at", "reads", "code"}, where
    code maps each repo to {"commit", "dirty", "dirty_hash", "dirty_files", "on_main",
    "behind_head"}; dirty_files is the evidence's list, null when it has none;
    behind_head counts commits between the tested commit and the checkout's
    HEAD, null when the checkout or commit can't be found.
  - caveats: lines under status.md's "Where a pass can mislead" that start with this id.
- may_mislead, untested, known_failing: the other lines of those status.md sections.
- tally: counts across behaviors (see TALLY below).

The harness's own scripts/framework/validate.py supplies the format parser, so this reads
any harness whose validate.py matches its feature files. It judges nothing: run
validate.py for format errors and stale-evidence warnings.

--html writes a self-contained page to PATH and prints the path instead.

Exits 0 with the output, 2 when the harness has no scripts/framework/validate.py or no
features/README.md, with the reason on a STOPPED: line on stderr.
"""

import argparse
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

BREAK = re.compile(r"Break-tested ([^:]+): (.*?)\.?\s+Evidence:")
BREAK_NO_EVIDENCE = re.compile(r"Break-tested ([^:]+): (.+)$")
NOT_BREAK_TESTED = re.compile(r"Not break-tested: (.+)$")
STATUS_LINE = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): ")
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
        raise Stopped(f"{path} is missing; this reads only harnesses setup-verification built")
    spec = importlib.util.spec_from_file_location("harness_validate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def feature_files(validate, features_dir):
    index = features_dir / "README.md"
    if not index.is_file():
        raise Stopped(f"no feature index at {index}")
    listed = [features_dir / name for name in validate.INDEX_LINK.findall(index.read_text())]
    others = sorted(p for p in features_dir.glob("*.md") if p.name not in ("README.md", validate.REQUIREMENTS))
    return [p for p in dict.fromkeys(listed + others) if p.is_file() and p.name != validate.REQUIREMENTS]


def id_lines(validate, lines):
    return {m.group(1): m.group(2) for line in lines if (m := validate.PROOF.match(line))}


def parse_proof(validate, harness_dir, sub_id, text):
    kind = validate.proof_kind(text)
    facts = {"proof": {"command": "check"}.get(kind, kind), "command": None, "reads": None,
             "break": None, "not_break_tested": None, "unreachable": None}
    if kind == "unreachable":
        facts["unreachable"] = text[len("Unreachable:"):].strip()
    if kind != "command":
        return facts
    command = validate.BACKTICK.search(text)
    facts["command"] = command.group(1)
    rest = text[command.end():].lstrip(". ")
    facts["reads"] = re.split(r"\s*(?:Not break-tested|Break-tested)", rest, maxsplit=1)[0].strip() or None
    if match := NOT_BREAK_TESTED.search(text):
        facts["not_break_tested"] = match.group(1)
    elif match := BREAK.search(text) or BREAK_NO_EVIDENCE.search(text):
        cite = validate.EVIDENCE_CITE.search(text)
        record = read_json(harness_dir / cite.group(1)) if cite else None
        planned = (record or {}).get("planned_break")
        aimed_at = planned.get("sub_features") if isinstance(planned, dict) else None
        caught = record and record.get("passed") is False and isinstance(aimed_at, list) and sub_id in aimed_at
        facts["break"] = {
            "date": match.group(1),
            "what": match.group(2),
            "evidence": cite.group(1) if cite else None,
            "on_hand": record is not None,
            "aimed_at": aimed_at,
            "failed_steps": [s.get("name") for s in validate.steps_judging(record, sub_id) if s.get("passed") is False]
            if caught else [],
        }
    return facts


def code_facts(validate, record, checkouts):
    """Describe recorded repo versions and how far they are behind their checkouts."""
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
    """Collect current behavior claims and the harness's recorded coverage caveats."""
    status = harness_dir / "status.md"
    text = status.read_text() if status.is_file() else ""
    _, body = validate.sections(text)
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
    """Collect proof and current-result facts for each mapped behavior."""
    validate = load_validator(harness_dir)
    project = validate.project_root(harness_dir)
    repos = validate.check_settings(harness_dir / "settings.md", []) if (harness_dir / "settings.md").is_file() else {}
    checkouts = {name: validate.resolve_repo(locator, project) for name, locator in repos.items()}
    results, bullets = latest_results(validate, harness_dir, checkouts)

    behaviors = []
    for path in feature_files(validate, harness_dir / "features"):
        text = path.read_text()
        _, body = validate.sections(text)
        title = next((line[2:] for line in text.splitlines() if line.startswith("# ")), path.stem)
        plans = id_lines(validate, body.get("Verification plan", []))
        proofs = id_lines(validate, body.get("How to prove it", []))
        for line in body.get("Sub-features", []):
            if not (match := validate.PROOF.match(line)):
                continue
            sub_id, behavior = match.groups()
            entry = {"id": sub_id, "feature": title, "behavior": behavior, "plan": plans.get(sub_id)}
            entry.update(parse_proof(validate, harness_dir, sub_id, proofs.get(sub_id, "No check yet.")))
            entry["result"] = results.get(sub_id)
            entry["caveats"] = [b[len(sub_id) + 2:] for b in bullets["may_mislead"] if b.startswith(sub_id + ": ")]
            behaviors.append(entry)

    for sub_id in {b["id"] for b in behaviors}:
        bullets["may_mislead"] = [b for b in bullets["may_mislead"] if not b.startswith(sub_id + ": ")]
    return {"harness": harness_dir.name, "behaviors": behaviors, **bullets, "tally": tally(behaviors)}


def tally(behaviors):
    counts = dict.fromkeys(TALLY, 0)
    counts["behaviors"] = len(behaviors)
    for b in behaviors:
        if b["proof"] == "check":
            counts["checked"] += 1
            if not b["break"]:
                counts["never_broken"] += 1
            elif b["break"]["on_hand"] and b["break"]["failed_steps"]:
                counts["caught_a_break"] += 1
            elif not b["break"]["on_hand"]:
                counts["break_not_on_hand"] += 1
        elif b["proof"] == "none":
            counts["no_check"] += 1
        else:
            counts["unreachable"] += 1
        result = b["result"]
        if not result:
            counts["no_result"] += 1
            continue
        counts[result["verdict"].lower().replace(" ", "_")] += 1
        if any(c["behind_head"] != 0 for c in result["code"].values()):
            counts["behind_head"] += 1
    return counts


def caught_cell(b):
    if b["proof"] == "none":
        return "No check yet"
    if b["proof"] == "unreachable":
        return f"Can't be checked: {b['unreachable']}"
    if b["not_break_tested"]:
        return f"Never shown failing: {b['not_break_tested']}"
    brk = b["break"]
    if not brk:
        return "Never shown failing"
    if not brk["on_hand"]:
        return f"Recorded {brk['date']}: {brk['what']} (proof not in this checkout)"
    if brk["aimed_at"] is not None and b["id"] not in brk["aimed_at"]:
        return f"Break on {brk['date']} was aimed at something else: {brk['what']}"
    if not brk["failed_steps"]:
        return f"Break on {brk['date']} did not fail a step that checks this: {brk['what']}"
    return f"Failed when we broke it ({brk['date']}): {brk['what']}"


def result_cell(b):
    result = b["result"]
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
    e = html.escape
    t = facts["tally"]
    rows = []
    for b in facts["behaviors"]:
        how = b["plan"] or b["reads"] or ""
        caveats = "".join(f"<li>{e(c)}</li>" for c in b["caveats"])
        proof = b["result"]["evidence"] if b["result"] and b["result"]["evidence"] else ""
        rows.append(
            f"<tr><td><b>{e(b['feature'])}</b><br>{e(b['behavior'])}<br><code>{e(b['id'])}</code></td>"
            f"<td>{e(how)}{f'<ul class=warn>{caveats}</ul>' if caveats else ''}</td>"
            f"<td>{e(caught_cell(b))}</td><td>{e(result_cell(b))}</td><td><code>{e(proof)}</code></td></tr>"
        )
    lists = "".join(
        f"<h2>{title}</h2><ul>{''.join(f'<li>{e(item)}</li>' for item in facts[key])}</ul>"
        for key, title in (("known_failing", "Known failing checks"), ("may_mislead", "Where a pass can mislead"),
                           ("untested", "Untested cases"))
        if facts[key]
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>What {e(facts['harness'])} checks</title>
<style>
body {{ font: 15px/1.45 system-ui, sans-serif; margin: 2rem; color: #1d1d1f; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #ddd; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #f5f5f7; }}
code {{ font-size: 13px; }}
.warn {{ color: #9a3412; margin: .3rem 0 0; padding-left: 1.1rem; }}
</style>
<h1>What {e(facts['harness'])} checks</h1>
<p>{t['behaviors']} behaviors. {t['caught_a_break']} have a check we've seen catch a deliberate break.
{t['never_broken'] + t['break_not_on_hand']} have a check we haven't seen fail here. {t['no_check'] + t['unreachable']} have no check.</p>
<p>This page shows what the harness records. Whether a check acts like a real user, and reads the result itself
rather than asking the app, is in its code: ask your agent to explain that check.</p>
<table>
<tr><th>Behavior</th><th>How it's checked</th><th>Seen catching a problem?</th><th>Latest result</th><th>Proof</th></tr>
{''.join(rows)}
</table>
{lists}
"""


def main():
    """Print recorded trust facts as JSON or write their HTML presentation."""
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
