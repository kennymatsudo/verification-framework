#!/usr/bin/env python3
"""Break each harness check in a scratch copy and report the ones no unit test catches.

A check is a top-level function in a non-test Python module under --harness whose name
matches --match (by default `*_problems`, `*_violations`, and `check_*`). Breaking it means
making its first statement return its "all clear" value: [] for a list, {} for a dict, True
for a bool, None for None. The value comes from the return annotation, or, with none, from
return statements that all build a list or all build a dict. A check with neither is SKIPPED.
If the unit suite still passes with the check broken, no test can tell a working check from
a useless one.

Run from the directory the suite runs in. Each break copies only the --copy paths (by default
the harness directory), skipping gitignored files, so name any other path the tests import.
Exits 1 when any check survives, 2 when the suite fails before anything is broken or a file
cannot be parsed, with the reason on a STOPPED: line for the latter.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

DEFAULT_MATCH = r"(_problems$|_violations$|^check_)"


class Stopped(Exception):
    pass


def is_test_file(path: Path) -> bool:
    """Whether a Python file holds tests or test plumbing rather than checks to break."""
    return path.name.startswith("test_") or path.name.endswith("_test.py") or path.name in {"conftest.py", "__init__.py"}


@dataclass
class Target:
    path: Path
    name: str
    line: int
    insert_at: int
    indent: int
    all_clear: str | None

    @property
    def label(self) -> str:
        return f"{self.path}:{self.line} {self.name}"

    @property
    def skipped_line(self) -> str:
        return f"SKIPPED {self.label}: no all-clear value from its annotation or returns"


def all_clear_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """The source text of the value a check returns when it finds nothing wrong, or None when it cannot be told."""
    if node.returns is not None:
        returns = ast.unparse(node.returns).replace("typing.", "")
        if returns.startswith(("list", "List", "Sequence", "Iterable")):
            return "[]"
        if returns.startswith(("dict", "Dict", "Mapping")):
            return "{}"
        if returns == "bool":
            return "True"
        if returns == "None":
            return "None"
        return None
    kinds = {value_kind(n.value) for n in ast.walk(node) if isinstance(n, ast.Return) and n.value is not None}
    return kinds.pop() if len(kinds) == 1 and None not in kinds else None


def value_kind(value: ast.expr) -> str | None:
    """The all-clear value for the type a return expression builds, when its shape shows it."""
    if isinstance(value, ast.IfExp):
        body, orelse = value_kind(value.body), value_kind(value.orelse)
        return body if body == orelse else None
    if isinstance(value, (ast.List, ast.ListComp)):
        return "[]"
    if isinstance(value, (ast.Dict, ast.DictComp)):
        return "{}"
    if isinstance(value, (ast.Compare, ast.BoolOp)) or (isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not)):
        return "True"
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return "True"
    return None


def find_targets(harness: Path, match: re.Pattern[str]) -> list[Target]:
    """Every top-level check function in the harness's non-test modules, with where to insert its early return."""
    targets = []
    for path in sorted(harness.rglob("*.py")):
        if is_test_file(path) or "node_modules" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            raise Stopped(f"cannot parse {path}: {error}") from error
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not match.search(node.name):
                continue
            body = node.body
            has_docstring = isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            first = body[1] if has_docstring and len(body) > 1 else body[0]
            targets.append(Target(path, node.name, node.lineno, first.lineno, first.col_offset, all_clear_value(node)))
    return targets


def unignored_files(path: Path) -> list[Path] | None:
    """The tracked and untracked files under path that Git does not ignore, or None outside a Git repo."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [Path(line) for line in out.splitlines() if line]


def make_copy(paths: list[Path]) -> Path:
    """Copy the paths, minus Git-ignored files, into a new scratch folder. The caller removes it."""
    root = Path(tempfile.mkdtemp(prefix="break-checks-"))
    for path in paths:
        files = unignored_files(path)
        if files is None:
            shutil.copytree(path, root / path, ignore=shutil.ignore_patterns("__pycache__", "node_modules", ".git"))
            continue
        for file in files:
            if file.is_file():
                (root / file).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, root / file)
    return root


def run_suite(suite: list[str], root: Path, timeout: int) -> tuple[bool, str]:
    """Run the unit suite in a scratch copy: whether it passed, and its last line of output."""
    try:
        done = subprocess.run(suite, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    output = (done.stdout + done.stderr).strip().splitlines()
    return done.returncode == 0, output[-1] if output else ""


def break_and_run(copy_paths: list[Path], suite: list[str], timeout: int, target: Target) -> tuple[Target, str]:
    """Break one check in a scratch copy and run the suite: CAUGHT when it fails, SURVIVED when it passes."""
    root = make_copy(copy_paths)
    try:
        copy = root / target.path
        lines = copy.read_text().splitlines(keepends=True)
        lines.insert(target.insert_at - 1, " " * target.indent + f"return {target.all_clear}  # broken by break_checks\n")
        copy.write_text("".join(lines))
        passed, _ = run_suite(suite, root, timeout)
        return target, "SURVIVED" if passed else "CAUGHT"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--harness", default="harness", type=Path, help="directory holding the checks (default harness)")
    parser.add_argument("--suite", help="unit suite command (default: python3 -m unittest discover -s <harness> -t .)")
    parser.add_argument("--copy", action="append", type=Path, help="path to copy into each scratch run; repeatable (default: --harness)")
    parser.add_argument("--match", default=DEFAULT_MATCH, help=f"regex on function names (default {DEFAULT_MATCH})")
    parser.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    parser.add_argument("--timeout", type=int, default=600, help="seconds per suite run")
    parser.add_argument("--list", action="store_true", help="list the checks that would be broken, run nothing")
    args = parser.parse_args()
    args.copy = args.copy or [args.harness]
    suite = shlex.split(args.suite) if args.suite else [sys.executable, "-m", "unittest", "discover", "-s", str(args.harness), "-t", "."]

    try:
        targets = find_targets(args.harness, re.compile(args.match))
    except Stopped as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    skipped = [target for target in targets if target.all_clear is None]
    targets = [target for target in targets if target.all_clear is not None]
    if args.list:
        for target in targets:
            print(f"{target.label} -> return {target.all_clear}")
        for target in skipped:
            print(target.skipped_line)
        return 0
    if not targets:
        print(f"No check functions matching {args.match} under {args.harness}.")
        return 2

    root = make_copy(args.copy)
    try:
        passed, tail = run_suite(suite, root, args.timeout)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if not passed:
        print(f"Baseline suite fails in a scratch copy ({tail}); fix that, or add the paths it needs with --copy.")
        return 2

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        outcomes = pool.map(lambda target: break_and_run(args.copy, suite, args.timeout, target), targets)
        results = sorted(outcomes, key=lambda result: (result[1], result[0].label))
    for target, verdict in results:
        print(f"{verdict} {target.label} -> return {target.all_clear}")
    for target in skipped:
        print(target.skipped_line)
    survived = sum(1 for _, verdict in results if verdict == "SURVIVED")
    print(f"\n{len(results)} checks broken, {survived} survived, {len(skipped)} skipped.")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
