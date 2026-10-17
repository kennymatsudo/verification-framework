#!/usr/bin/env python3
"""List Python test and check code shaped like a pass that cannot fail.

Each hit is a lead, not a verdict: the agent reads the code and decides. Kinds:

  no-assert      a test that asserts nothing, directly or through a helper it calls
  only-exists    a test whose only assertions check that something came back
  self-compare   an assertion comparing an expression with itself, or asserting a constant
  skip           a skip or xfail; each one hides a test until someone removes it
  swallow        a broad except in harness code that neither re-raises nor records a failure

Understands unittest (self.assert*, self.fail, skipTest) and pytest (assert, pytest.raises,
pytest.fail, pytest.skip, @pytest.mark.skip/skipif/xfail). Run from the project root.
Exits 1 when there are hits, 2 when a file cannot be parsed, with the reason on a STOPPED: line.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

EXISTENCE_ONLY = {"assertIsNotNone", "assertTrue", "assertIsInstance"}
SKIPS = {"skip", "skipIf", "skipUnless", "expectedFailure", "skipTest", "skipif", "xfail"}
FAILURE_WORDS = ("fail", "problem", "violation", "error", "raise")


def is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def asserting_nodes(node: ast.AST) -> list[ast.AST]:
    """Assertion calls, pytest.raises/fail calls, and bare assert statements."""
    found: list[ast.AST] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Assert):
            found.append(n)
        elif isinstance(n, ast.Call) and (call_name(n).startswith("assert") or call_name(n) in {"fail", "raises"}):
            found.append(n)
    return found


def existence_only(n: ast.AST) -> bool:
    if isinstance(n, ast.Call):
        return call_name(n) in EXISTENCE_ONLY
    if isinstance(n, ast.Assert):
        test = n.test
        if isinstance(test, (ast.Name, ast.Attribute, ast.Call)):
            return True
        return (
            isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None
        )
    return False


def self_compare(n: ast.AST) -> bool:
    if isinstance(n, ast.Call):
        args = [ast.dump(a) for a in n.args]
        if len(args) >= 2 and args[0] == args[1]:
            return True
        return call_name(n) in {"assertTrue", "assertFalse"} and bool(n.args) and isinstance(n.args[0], ast.Constant)
    if isinstance(n, ast.Assert):
        test = n.test
        if isinstance(test, ast.Constant):
            return True
        return isinstance(test, ast.Compare) and len(test.comparators) == 1 and ast.dump(test.left) == ast.dump(test.comparators[0])
    return False


def helpers_that_assert(tree: ast.Module) -> set[str]:
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test") and asserting_nodes(node)
    }


def decorator_name(decorator: ast.expr) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")


def scan_test_file(path: Path) -> list[str]:
    """The no-assert, only-exists, self-compare, and skip hits in one test file."""
    tree = ast.parse(path.read_text())
    helpers = helpers_that_assert(tree)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                if decorator_name(decorator) in SKIPS:
                    hits.append(f"skip {path}:{node.lineno} {node.name}")
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test")):
            continue
        where = f"{path}:{node.lineno} {node.name}"
        found = asserting_nodes(node)
        uses_helper = any(isinstance(n, ast.Call) and call_name(n) in helpers for n in ast.walk(node))
        uses_helper = uses_helper or any(isinstance(n, ast.Raise) for n in ast.walk(node))
        if not found and not uses_helper:
            hits.append(f"no-assert {where}")
        elif found and not uses_helper and all(existence_only(n) for n in found):
            hits.append(f"only-exists {where}")
        for n in found:
            if self_compare(n):
                hits.append(f"self-compare {path}:{n.lineno} in {node.name}")
        body_nodes = [n for stmt in node.body for n in ast.walk(stmt)]
        for n in body_nodes:
            if isinstance(n, ast.Call) and call_name(n) in {"skipTest", "skip", "xfail"}:
                hits.append(f"skip {path}:{n.lineno} in {node.name}")
    return hits


def is_broad(handler: ast.ExceptHandler) -> bool:
    kind = handler.type
    return kind is None or (isinstance(kind, ast.Name) and kind.id in {"Exception", "BaseException"})


def scan_harness_file(path: Path) -> list[str]:
    """The swallow hits in one non-test file."""
    tree = ast.parse(path.read_text())
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ExceptHandler) and is_broad(node)):
            continue
        body = ast.unparse(ast.Module(body=node.body, type_ignores=[])).lower()
        if any(isinstance(n, ast.Raise) for n in ast.walk(node)) or any(word in body for word in FAILURE_WORDS):
            continue
        hits.append(f"swallow {path}:{node.lineno}")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("harness")], help="directories to scan (default harness)")
    args = parser.parse_args()
    hits = []
    for root in args.paths:
        for path in sorted(root.rglob("*.py")):
            if "node_modules" in path.parts:
                continue
            try:
                hits += scan_test_file(path) if is_test_file(path) else scan_harness_file(path)
            except (SyntaxError, UnicodeDecodeError, OSError) as error:
                print(f"STOPPED: cannot parse {path}: {error}", file=sys.stderr)
                return 2
    print("\n".join(hits) if hits else "No smells found.")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
