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
    """The name a call uses, without its receiver: `assertEqual` for `self.assertEqual(...)`."""
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def asserting_nodes(node: ast.AST) -> list[ast.AST]:
    """Assertion calls, pytest.raises/fail calls, and bare assert statements."""
    found: list[ast.AST] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Assert):
            found.append(inner)
        elif isinstance(inner, ast.Call) and (call_name(inner).startswith("assert") or call_name(inner) in {"fail", "raises"}):
            found.append(inner)
    return found


def existence_only(assertion: ast.AST) -> bool:
    """Whether an assertion only checks that something came back: truthy, an instance, or not None."""
    if isinstance(assertion, ast.Call):
        return call_name(assertion) in EXISTENCE_ONLY
    if isinstance(assertion, ast.Assert):
        test = assertion.test
        if isinstance(test, (ast.Name, ast.Attribute, ast.Call)):
            return True
        return (
            isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None
        )
    return False


def self_compare(assertion: ast.AST) -> bool:
    """Whether an assertion compares an expression with itself or asserts a constant, so it can never fail."""
    if isinstance(assertion, ast.Call):
        args = [ast.dump(arg) for arg in assertion.args]
        if len(args) >= 2 and args[0] == args[1]:
            return True
        return call_name(assertion) in {"assertTrue", "assertFalse"} and bool(assertion.args) and isinstance(assertion.args[0], ast.Constant)
    if isinstance(assertion, ast.Assert):
        test = assertion.test
        if isinstance(test, ast.Constant):
            return True
        return isinstance(test, ast.Compare) and len(test.comparators) == 1 and ast.dump(test.left) == ast.dump(test.comparators[0])
    return False


def helpers_that_assert(tree: ast.Module) -> set[str]:
    """The names of the non-test functions in a module that assert something themselves."""
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test") and asserting_nodes(node)
    }


def decorator_name(decorator: ast.expr) -> str:
    """A decorator's last name part: `skip` for `@pytest.mark.skip(...)`."""
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
        inner_nodes = list(ast.walk(node))
        # A test that calls an asserting helper, or raises itself, can fail without an assertion of its own.
        can_fail_otherwise = any(
            isinstance(inner, ast.Raise) or (isinstance(inner, ast.Call) and call_name(inner) in helpers)
            for inner in inner_nodes
        )
        if not found and not can_fail_otherwise:
            hits.append(f"no-assert {where}")
        elif found and not can_fail_otherwise and all(existence_only(assertion) for assertion in found):
            hits.append(f"only-exists {where}")
        for assertion in found:
            if self_compare(assertion):
                hits.append(f"self-compare {path}:{assertion.lineno} in {node.name}")
        for inner in inner_nodes:
            if isinstance(inner, ast.Call) and call_name(inner) in {"skipTest", "skip", "xfail"}:
                hits.append(f"skip {path}:{inner.lineno} in {node.name}")
    return hits


def is_broad(handler: ast.ExceptHandler) -> bool:
    """Whether an except clause catches everything: bare, Exception, or BaseException."""
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
        if any(isinstance(inner, ast.Raise) for inner in ast.walk(node)) or any(word in body for word in FAILURE_WORDS):
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
