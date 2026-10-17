#!/usr/bin/env python3
"""The exploration ledger: one JSON line per round of explore-bugs.

Each round starts in a fresh session, so the ledger is the loop's only memory:
what was tried, what behavior it reached, what it cost, and what is still open.
The ledger lives at evidence/exploration-ledger.jsonl inside the harness.

Usage:
    ledger.py --harness HARNESS_DIR summary          # where the loop stands, as JSON
    ledger.py --harness HARNESS_DIR add '<json>'     # append one round
    ledger.py --harness HARNESS_DIR cleaned ID ...   # record resources deleted
    ledger.py --harness HARNESS_DIR close ROUND ...  # record findings or leads resolved

Exits 0 on success, 2 when it cannot run or a row is invalid.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

VERDICTS = ("finding", "known", "no-break", "lead", "invalid", "planted-caught", "planted-missed")
REQUIRED = ("sweep", "hypothesis", "kind", "command", "signature", "verdict")
# Fields the ledger writes itself: round numbering, timestamps, and the cleanup and close lines.
RESERVED = ("round", "at", "cleaned", "closed")
OPEN = ("finding", "lead")
KINDS = ["timing", "order", "identity", "input-shape", "lifecycle", "external-side", "code-reading"]
# Rounds in a row with no new signature before the loop must change approach.
STALE_ROUNDS = 3

# The row format lives here, beside the checks that enforce it, so the skill can point at --help
# instead of restating fields that could drift from what add accepts.
FIELDS = {
    "sweep": "the sweep's date: today, unless the user named one",
    "hypothesis": "the round's cases, one clause each",
    "kind": f"one of {', '.join(KINDS)}, or planted for a calibration round",
    "command": "the command that ran the round",
    "signature": "list of short stable strings for the failed checks, broken invariants, and anomaly kinds",
    "verdict": "one of the verdicts below",
}
OPTIONAL = {
    "reproduced": '"2/2 at path:line" for a confirmed break, or "k/3"',
    "evidence": "the evidence file path",
    "finding": "the promoted finding",
    "created_open": "IDs of resources the round created and has not yet deleted",
}
MEANINGS = {
    "finding": "a break was confirmed and promoted",
    "known": "every break matched a known issue",
    "no-break": "nothing broke",
    "lead": "an anomaly that has not repeated or broken an invariant yet",
    "invalid": "the environment or the harness caused the result",
    "planted-caught": "a calibration round found the planted break",
    "planted-missed": "a calibration round missed the planted break",
}


def row_help():
    def block(title, entries):
        return [title] + [f"  {key:<16}{text}" for key, text in entries.items()]
    lines = block("Required fields:", FIELDS) + block("Optional, when they apply:", OPTIONAL)
    lines += block("Verdicts:", {verdict: MEANINGS[verdict] for verdict in VERDICTS})
    return "\n".join(lines)


class LedgerError(ValueError):
    pass


def ledger_path(harness):
    """The harness's ledger file; raises LedgerError when the folder has no rules.md."""
    if not (harness / "rules.md").is_file():
        raise LedgerError(f"no verification harness at {harness}")
    return harness / "evidence" / "exploration-ledger.jsonl"


def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def rounds(lines):
    return [line for line in lines if "cleaned" not in line and "closed" not in line]


def closed_rounds(lines):
    return {number for line in lines for number in line.get("closed", [])}


def append(path, entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as ledger:
        ledger.write(json.dumps(entry) + "\n")
    return entry


def add(row, path):
    """Check one round's row and append it with its round number and time. Returns the line written."""
    if not isinstance(row, dict):
        raise LedgerError("the row must be a JSON object")
    missing = [key for key in REQUIRED if key not in row]
    if missing:
        raise LedgerError(f"missing {', '.join(missing)}")
    reserved = [key for key in RESERVED if key in row]
    if reserved:
        raise LedgerError(f"leave {', '.join(reserved)} out of the row; ledger.py writes them")
    if row["kind"] not in KINDS and row["kind"] != "planted":
        raise LedgerError(f"kind must be one of {', '.join(KINDS)}, or planted")
    if row["verdict"] not in VERDICTS:
        raise LedgerError(f"verdict must be one of {', '.join(VERDICTS)}")
    # A calibration round's verdict says whether it caught its planted break; summary counts on the pairing.
    if (row["kind"] == "planted") != row["verdict"].startswith("planted-"):
        raise LedgerError("kind planted goes with verdict planted-caught or planted-missed, and only with them")
    for field in ("signature", "created_open"):
        value = row.get(field, [])
        if not isinstance(value, list) or not all(isinstance(part, str) for part in value):
            raise LedgerError(f"{field} must be a list of strings")
    number = len(rounds(read(path))) + 1
    return append(path, {"round": number, "at": datetime.now().isoformat(timespec="seconds"), **row})


def close(numbers, path):
    """Record findings whose check now passes, and leads a later round promoted, matched, or dropped."""
    lines = read(path)
    still_open = {row["round"] for row in rounds(lines) if row["verdict"] in OPEN} - closed_rounds(lines)
    for number in numbers:
        if number not in still_open:
            raise LedgerError(f"round {number} is not an open finding or lead")
    return append(path, {"at": datetime.now().isoformat(timespec="seconds"), "closed": numbers})


def summary(lines):
    """A round is new when its signature, the set of behaviors it reached, was never reached before."""
    rows = rounds(lines)
    deleted = {item for line in lines for item in line.get("cleaned", [])}
    closed = closed_rounds(lines)
    sweep = rows[-1]["sweep"] if rows else None
    # Planted rounds rediscover a known break on purpose, so they never count as new.
    seen, new_flags = set(), []
    for row in (row for row in rows if row["kind"] != "planted"):
        signature = frozenset(row["signature"])
        new_flags.append(signature not in seen)
        seen.add(signature)
    since_new = 0
    for is_new in reversed(new_flags):
        if is_new:
            break
        since_new += 1
    tried = Counter(row["kind"] for row in rows)
    planted = [row for row in rows if row["kind"] == "planted"]
    return {
        "sweep": sweep,
        "rounds": len(rows),
        "rounds_since_new_signature": since_new,
        "must_change_approach": since_new >= STALE_ROUNDS,
        "kinds_tried": {kind: tried.get(kind, 0) for kind in KINDS},
        "planted_caught": f"{sum(row['verdict'] == 'planted-caught' for row in planted)}/{len(planted)}",
        "open_findings": [
            {key: row.get(key) for key in ("round", "hypothesis", "verdict", "reproduced", "finding", "evidence")}
            for row in rows if row["verdict"] in OPEN and row["round"] not in closed
        ],
        "to_clean": sorted({item for row in rows for item in row.get("created_open", [])} - deleted),
        "recent": [
            {key: row.get(key) for key in ("round", "kind", "hypothesis", "verdict", "signature")}
            for row in rows[-5:]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", type=Path, required=True, help="the verification harness directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("summary")
    adding = commands.add_parser("add", epilog=row_help(), formatter_class=argparse.RawDescriptionHelpFormatter)
    adding.add_argument("row", help="one round as a JSON object")
    cleaning = commands.add_parser("cleaned")
    cleaning.add_argument("ids", nargs="+", help="IDs of resources this loop created and has now deleted")
    closing = commands.add_parser("close")
    closing.add_argument("rounds", nargs="+", type=int, help="rounds whose finding or lead is resolved")
    args = parser.parse_args()
    try:
        path = ledger_path(args.harness.resolve())
        if args.command == "summary":
            result = summary(read(path))
        elif args.command == "cleaned":
            entry = {"at": datetime.now().isoformat(timespec="seconds"), "cleaned": args.ids}
            result = append(path, entry)
        elif args.command == "close":
            result = close(args.rounds, path)
        else:
            result = add(json.loads(args.row), path)
    except (LedgerError, json.JSONDecodeError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
