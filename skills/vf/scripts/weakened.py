#!/usr/bin/env python3
"""List every way the harness's tests and checks got weaker since a commit.

Compares the working tree with --since (by default the last commit titled "Audit harness
checks", else the last commit before 30 days ago) and prints:

  deleted-test   a test function that no longer exists
  fewer-asserts  a file that lost more assertion lines than it gained
  removed-assert each assertion line removed, with its old text
  new-skip       a skip or xfail that was added
  check-changed  a check function (a top-level def matching --match) whose body or decorators
                 changed, or a changed file that does not parse, to read by hand

Each line is a lead. A weakening is fine only when the behavior it guarded changed on purpose;
a bug never changes the expectation. Python files only. Run from the project root.
Exits 1 when there are leads, 2 when it cannot run, with the reason on a STOPPED: line.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_MATCH = r"(_problems$|_violations$|^check_)"
AUDIT_TITLE = "^Audit harness checks"
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def (test_\w+)")
ASSERT = re.compile(r"(\bself\.assert\w+|\bself\.fail\(|^\s*assert\s|\bpytest\.(raises|fail)\()")
SKIP = re.compile(r"(@\S*skip|\.skipTest\(|expectedFailure|mark\.xfail|pytest\.(skip|xfail)\()")
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)")
UNPARSED = "(does not parse, so read its diff by hand)"
# Most serious kind first, so a reader sees the leads that matter before the ones that explain them.
LEAD_ORDER = ["deleted-test", "fewer-asserts", "new-skip", "check-changed", "removed-assert"]


class Stopped(Exception):
    pass


def git(*args: str) -> str:
    """Git's output for the command, run in the current directory; CalledProcessError when it fails."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def default_since() -> tuple[str, str]:
    """The commit to compare against when --since is not given, and why: the last audit, else 30 days ago."""
    audit = git("log", "-1", "--format=%H", f"--grep={AUDIT_TITLE}", "--", ".").strip()
    if audit:
        return audit, "last Audit harness checks commit"
    return git("rev-list", "-1", "--before=30 days ago", "HEAD").strip(), "30 days ago (no earlier audit)"


def starting_commit(since: str | None) -> tuple[str, str]:
    """The commit to compare against, and why it was chosen."""
    why = "--since"
    if not since:
        since, why = default_since()
        if not since:
            raise Stopped("no Audit harness checks commit and no commit older than 30 days; pass --since <commit>")
    try:
        git("rev-parse", "--verify", "--quiet", f"{since}^{{commit}}")
    except subprocess.CalledProcessError as error:
        raise Stopped(f"{since} is not a commit in this repo {error.stderr.strip()}".strip()) from error
    return since, why


def check_spans(path: str, rev: str | None, match: re.Pattern[str]) -> list[tuple[int, int, str]]:
    """First line, last line, and name of each top-level check function in a file at rev (None = working tree).

    A span starts at the function's first decorator. A file that does not parse is one span named UNPARSED,
    so every change in it becomes a lead.
    """
    try:
        text = git("show", f"{rev}:./{path}") if rev else Path(path).read_text()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [(1, max(len(text.splitlines()), 1), UNPARSED)]
    return [
        (min([node.lineno] + [decorator.lineno for decorator in node.decorator_list]), node.end_lineno, node.name)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and match.search(node.name)
    ]


def owning_check(spans: list[tuple[int, int, str]], line: int) -> str | None:
    """The name of the check function whose span holds the line, or None when no check does."""
    return next((name for first, last, name in spans if first <= line <= last), None)


def weakening_leads(since: str, paths: list[str], match: re.Pattern[str]) -> list[str]:
    """Every lead between since and the working tree, most serious kind first."""
    leads: list[str] = []
    removed_tests: dict[str, str] = {}
    added_tests: set[str] = set()
    for rel in git("diff", "--relative", "--name-only", since, "--", *paths).split():
        if not rel.endswith(".py"):
            continue
        diff = git("diff", "-U0", since, "--", rel)
        old_checks, new_checks = check_spans(rel, since, match), check_spans(rel, None, match)
        changed: set[str] = set()
        removed_asserts = added_asserts = 0
        old_line = new_line = 0
        for line in diff.splitlines():
            if hunk := HUNK.match(line):
                old_line, new_line = int(hunk.group(1)), int(hunk.group(2))
                continue
            if line.startswith(("---", "+++")):
                continue
            if line.startswith("-"):
                text = line[1:]
                if m := TEST_DEF.match(text):
                    removed_tests[m.group(1)] = rel
                if ASSERT.search(text):
                    removed_asserts += 1
                    leads.append(f"removed-assert {rel}:{old_line} {text.strip()[:140]}")
                if name := owning_check(old_checks, old_line):
                    changed.add(name)
                old_line += 1
            elif line.startswith("+"):
                text = line[1:]
                if m := TEST_DEF.match(text):
                    added_tests.add(m.group(1))
                if ASSERT.search(text):
                    added_asserts += 1
                if SKIP.search(text):
                    leads.append(f"new-skip {rel}:{new_line} {text.strip()[:140]}")
                if name := owning_check(new_checks, new_line):
                    changed.add(name)
                new_line += 1
        if removed_asserts > added_asserts:
            leads.append(f"fewer-asserts {rel}: -{removed_asserts} +{added_asserts}")
        leads += [f"check-changed {rel} {name}" for name in sorted(changed)]

    leads += [f"deleted-test {path} {name}" for name, path in sorted(removed_tests.items()) if name not in added_tests]
    leads.sort(key=lambda lead: LEAD_ORDER.index(lead.split()[0]))
    return leads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since")
    parser.add_argument("--path", action="append", help="path to compare; repeatable (default harness)")
    parser.add_argument("--match", default=DEFAULT_MATCH, help=f"regex on check function names (default {DEFAULT_MATCH})")
    args = parser.parse_args()
    try:
        since, why = starting_commit(args.since)
        print(f"Since {since[:12]} ({why})")
        leads = weakening_leads(since, args.path or ["harness"], re.compile(args.match))
    except (Stopped, FileNotFoundError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"STOPPED: {' '.join(error.cmd)} failed: {error.stderr.strip()}", file=sys.stderr)
        return 2
    print("\n".join(leads) if leads else "No weakening found.")
    return 1 if leads else 0


if __name__ == "__main__":
    sys.exit(main())
