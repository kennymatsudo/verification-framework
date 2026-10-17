#!/usr/bin/env python3
"""Print the Git state of every repo the harness's settings.md lists, as the evidence 'code' field.

Usage: code_state.py [HARNESS_DIR] [--checkout NAME=PATH ...]

HARNESS_DIR defaults to the directory above this script. Prints one JSON object
keyed by repo name, each entry {"commit", "branch", "dirty", "on_main"}, ready to
copy into an evidence file's "code" field or a launch record. Every harness tool
that records code versions calls this instead of reading Git itself, so the
doctor, the checks, and check.py agree on what each field means.

- commit: the full commit HEAD points at.
- branch: the checked-out branch, or null on a detached HEAD.
- dirty: a modified, staged, or untracked file outside the harness directory;
  files Git ignores don't count.
- on_main: whether the commit is on the repo's default branch: origin/HEAD when
  the clone has it, else a local main, else master. null when none exists.

--checkout points one repo at another checkout, such as a scratch worktree
holding a planned break. This reports the checkout on disk, not what a running
process loaded; the doctor still establishes that, for example by saving this
output at launch and comparing it with a fresh run.

Exits 0 with the JSON, 2 when settings.md lists no repos, has an invalid repo
line, or a repo cannot be found or has no commit, with the reason on a STOPPED: line on stderr.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# Loaded by path so this runs under `python3 -I`, which leaves the script's own directory off sys.path.
_SPEC = importlib.util.spec_from_file_location("harness_check", Path(__file__).with_name("check.py"))
check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check)


class StateError(Exception):
    pass


def listed_repos(harness_dir):
    settings = harness_dir / "settings.md"
    try:
        _, body = check.sections(settings.read_text())
    except OSError as error:
        raise StateError(f"cannot read {settings}: {error}") from error
    repos, errors = check.parse_repos(body)
    if errors:
        raise StateError("; ".join(errors))
    if not repos:
        raise StateError(f"{settings} lists no repos under '## Repos'")
    return repos


def default_branch(checkout):
    """The checkout's default branch: origin/HEAD when the clone has it, else a local main, else master, else None."""
    remote = check.git(checkout, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if remote:
        return remote
    for name in ("main", "master"):
        if check.git(checkout, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    return None


def checkout_state(checkout, harness_dir):
    commit = check.git(checkout, "rev-parse", "--verify", "--quiet", "HEAD")
    if not commit:
        raise StateError(f"{checkout} has no commit")
    base = default_branch(checkout)
    on_main = None
    if base:
        ancestor = subprocess.run(
            ["git", "-C", str(checkout), "merge-base", "--is-ancestor", commit, base], capture_output=True
        )
        on_main = {0: True, 1: False}.get(ancestor.returncode)
    changed = check.uncommitted_files(checkout, harness_dir)
    if changed is None:
        raise StateError(f"git status failed in {checkout}")
    return {
        "commit": commit,
        "branch": check.git(checkout, "symbolic-ref", "--short", "-q", "HEAD"),
        "dirty": bool(changed),
        "on_main": on_main,
    }


def code_state(harness_dir, overrides):
    """The code entry for every repo settings.md lists, with overrides naming another checkout for a repo."""
    harness_dir = harness_dir.resolve()
    repos = listed_repos(harness_dir)
    unknown = sorted(set(overrides) - set(repos))
    if unknown:
        raise StateError(f"--checkout names {', '.join(unknown)}, which settings.md does not list")
    repo_root = Path(check.git(harness_dir, "rev-parse", "--show-toplevel") or harness_dir)
    state = {}
    for name, locator in repos.items():
        if name in overrides:
            path = overrides[name].resolve()
            checkout = path if check.git(path, "rev-parse", "--show-toplevel") else None
        else:
            checkout = check.resolve_repo(locator, repo_root)
        if not checkout:
            raise StateError(f"{name}: no Git checkout at {overrides.get(name, locator)}")
        state[name] = checkout_state(checkout, harness_dir)
    return state


def parse_checkout(value):
    name, sep, path = value.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got {value!r}")
    return name, Path(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("harness_dir", nargs="?", default=Path(__file__).resolve().parent.parent, type=Path)
    parser.add_argument(
        "--checkout", action="append", default=[], type=parse_checkout, metavar="NAME=PATH",
        help="report repo NAME from the checkout at PATH, such as a scratch worktree; repeatable",
    )
    args = parser.parse_args()
    try:
        state = code_state(args.harness_dir, dict(args.checkout))
    except StateError as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
