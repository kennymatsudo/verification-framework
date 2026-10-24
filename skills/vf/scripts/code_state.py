#!/usr/bin/env python3
"""Print the Git state of every repo the harness's settings.md lists, as the evidence 'code' field.

Usage: code_state.py [HARNESS_DIR] [--checkout NAME=PATH ...]

HARNESS_DIR defaults to the harness this script sits in, at scripts/framework/. Prints one JSON object
keyed by repo name, each entry {"commit", "branch", "dirty", "dirty_hash", "on_main"}, ready to
copy into an evidence file's "code" field or a launch record. Every harness tool
that records code versions calls this instead of reading Git itself, so the
doctor, the checks, and validate.py agree on what each field means.

- commit: the full commit HEAD points at.
- branch: the checked-out branch, or null on a detached HEAD.
- dirty: a modified, staged, or untracked file outside the harness directory and
  the framework skill copies sync wrote beside it;
  files Git ignores don't count.
- dirty_hash: SHA-256 of staged and unstaged diffs and untracked contents,
  excluding the harness; null when clean. Capture this when the process loads its code.
- on_main: whether the commit is on the repo's default branch: origin/HEAD when
  the clone has it, else a local main, else master. null when none exists.

A locator that names a folder inside a checkout, such as the app's own folder in
a monorepo, scopes dirty and dirty_hash to that folder; commit, branch, and
on_main stay the checkout's. Locators resolve from the project root, the folder
holding the skills directory the harness sits in.

--checkout points one repo at another checkout, such as a scratch worktree
holding a planned break. This reports the checkout on disk, not what a running
process loaded; the doctor still establishes that, for example by saving this
output at launch and comparing it with a fresh run.

While break_session.py has a planned break session open on a repo, ordinary code
recording refuses, including --checkout overrides. Only the owning harness may
record the scratch copy with VERIFY_PLANNED_BREAK set. Commands break_session.py
runs from settings.md set VERIFY_BREAK_SESSION to the session's repo name and get
the checkout the app is being pointed at. An override must name that same checkout.

Exits 0 with the JSON, 2 when settings.md lists no repos, has an invalid repo
line, a repo cannot be found or has no commit, or a session is open and the run
is not a planned break, with the reason on a STOPPED: line on stderr.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def _load(name, filename):
    # Loaded by path so this runs under `python3 -I`, which leaves the script's own directory off sys.path.
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = _load("harness_validate", "validate.py")


class StateError(Exception):
    pass


def listed_repos(harness_dir):
    """The repos settings.md lists by name, each with its locator; StateError when it lists none or one is invalid."""
    settings = harness_dir / "settings.md"
    try:
        _, body = validate.sections(settings.read_text())
    except OSError as error:
        raise StateError(f"cannot read {settings}: {error}") from error
    repos, errors = validate.parse_repos(body)
    if errors:
        raise StateError("; ".join(errors))
    if not repos:
        raise StateError(f"{settings} lists no repos under '## Repos'")
    return repos


def default_branch(checkout):
    """The checkout's default branch: origin/HEAD when the clone has it, else a local main, else master, else None."""
    remote = validate.git(checkout, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if remote:
        return remote
    for name in ("main", "master"):
        if validate.git(checkout, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    return None


def dirty_hash(checkout, harness_dir):
    """A SHA-256 over the checkout's uncommitted changes, so evidence can name them without holding their contents."""
    paths = validate.source_pathspec(checkout, harness_dir)
    digest = hashlib.sha256()

    def include(value):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    def output(*args):
        result = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True)
        if result.returncode:
            raise StateError(f"cannot fingerprint changes in {checkout}")
        return result.stdout

    for mode in (["--cached"], []):
        include(output("diff", "--binary", "--no-ext-diff", "--no-textconv", "--full-index", *mode, "--", *paths))
    untracked = output("ls-files", "--others", "--exclude-standard", "-z", "--", *paths)
    for name in sorted(part for part in untracked.split(b"\0") if part):
        include(name)
        path = checkout / os.fsdecode(name)
        try:
            if path.is_symlink():
                include(b"symlink")
                include(os.fsencode(os.readlink(path)))
            else:
                include(b"executable" if path.stat().st_mode & 0o111 else b"file")
                include(path.read_bytes())
        except OSError as error:
            raise StateError(f"cannot fingerprint {path}: {error}") from error
    return digest.hexdigest()


def checkout_state(checkout, harness_dir):
    """One repo's entry for the evidence code field: commit, branch, dirty, dirty_hash, and on_main, ignoring the harness's own files."""
    commit = validate.git(checkout, "rev-parse", "--verify", "--quiet", "HEAD")
    if not commit:
        raise StateError(f"{checkout} has no commit")
    base = default_branch(checkout)
    on_main = None
    if base:
        ancestor = subprocess.run(
            ["git", "-C", str(checkout), "merge-base", "--is-ancestor", commit, base], capture_output=True
        )
        on_main = {0: True, 1: False}.get(ancestor.returncode)
    changed = validate.uncommitted_files(checkout, harness_dir)
    if changed is None:
        raise StateError(f"git status failed in {checkout}")
    return {
        "commit": commit,
        "branch": validate.git(checkout, "symbolic-ref", "--short", "-q", "HEAD"),
        "dirty": bool(changed),
        "dirty_hash": dirty_hash(checkout, harness_dir) if changed else None,
        "on_main": on_main,
    }


def session_folder(checkout):
    """Where break_session.py keeps a repo's planned break session: inside the repo's shared Git folder,
    which every worktree of it sees and nothing commits. None when the checkout is not a Git repo."""
    common = validate.git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common) / "verify-break-session" if common else None


def open_session(checkout):
    """The repo's open planned break session, or None."""
    folder = session_folder(checkout)
    if not folder:
        return None
    path = folder / "session.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise StateError(f"cannot read the break session at {path}: {error}") from error


def require_session_owner(session, harness_dir):
    """StateError unless the open session belongs to this harness, since only its owner may run, record, or end it."""
    owner = Path(session["harness"])
    if owner != harness_dir.resolve():
        raise StateError(
            f"the break session belongs to {owner}; close it with "
            f"`python3 scripts/framework/vf.py break --harness {owner} end {session['repo']}`"
        )


def session_checkout(name, session, harness_dir):
    """The checkout this run records while a session is open, or StateError when it may not record one."""
    require_session_owner(session, harness_dir)
    on_scratch = session["app_checkout"] == session["scratch"]
    if os.environ.get("VERIFY_BREAK_SESSION") == session["repo"] or (on_scratch and os.environ.get("VERIFY_PLANNED_BREAK")):
        return Path(session["app_checkout"])
    raise StateError(
        f"{name}: a planned break session is open, so the app may be running the scratch copy at {session['scratch']}. "
        f"Only planned break runs may record code until `python3 scripts/framework/vf.py break end {name}` closes it"
    )


def recorded_checkout(name, locator, override, project, harness_dir):
    """The checkout whose state this run records for one repo: the locator's, the --checkout override's, or,
    while a planned break session is open on either, the checkout the session allows. StateError when there is none."""
    checkout = validate.resolve_repo(locator, project)
    session = open_session(checkout) if checkout else None
    if override is not None:
        path = override.resolve()
        checkout = path if validate.git(path, "rev-parse", "--show-toplevel") else None
        if not session and checkout:
            session = open_session(checkout)
    if session:
        expected = session_checkout(name, session, harness_dir)
        if override is not None and checkout != expected:
            raise StateError(f"{name}: --checkout must name the session checkout at {expected}")
        checkout = expected
    if not checkout:
        raise StateError(f"{name}: no Git checkout at {override if override is not None else locator}")
    return checkout


def break_session_repo(harness_dir):
    """The repo whose planned break session this harness has open on its scratch copy, which is the repo a
    planned break run edited. StateError unless there is exactly one, so a break can't be recorded outside a session."""
    harness_dir = harness_dir.resolve()
    project = validate.project_root(harness_dir)
    found = []
    for name, locator in listed_repos(harness_dir).items():
        checkout = validate.resolve_repo(locator, project)
        session = open_session(checkout) if checkout else None
        if session and Path(session["harness"]) == harness_dir and session["app_checkout"] == session["scratch"]:
            found.append(name)
    if not found:
        raise StateError("VERIFY_PLANNED_BREAK is set but this harness has no break session open; "
                         "run the break through `vf.py break run`")
    if len(found) > 1:
        raise StateError(f"break sessions are open on {', '.join(found)}, so this break can't name the repo it edited; "
                         f"end all but the one holding the break")
    return found[0]


def code_state(harness_dir, overrides):
    """The code entry for every repo settings.md lists, with overrides naming another checkout for a repo."""
    harness_dir = harness_dir.resolve()
    repos = listed_repos(harness_dir)
    unknown = sorted(set(overrides) - set(repos))
    if unknown:
        raise StateError(f"--checkout names {', '.join(unknown)}, which settings.md does not list")
    project = validate.project_root(harness_dir)

    def state(name, locator):
        return checkout_state(recorded_checkout(name, locator, overrides.get(name), project, harness_dir), harness_dir)

    # Repos are read side by side, since each takes seconds in a large checkout; results and the first error
    # reported follow the settings order, so a run reads the same however the reads finish.
    with ThreadPoolExecutor() as pool:
        reads = {name: pool.submit(state, name, locator) for name, locator in repos.items()}
    return {name: read.result() for name, read in reads.items()}


def parse_checkout(value):
    """A --checkout argument as (repo name, path); ArgumentTypeError unless it is NAME=PATH."""
    name, sep, path = value.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got {value!r}")
    return name, Path(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("harness_dir", nargs="?", default=Path(__file__).resolve().parents[2], type=Path)
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
