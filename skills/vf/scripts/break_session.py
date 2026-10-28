#!/usr/bin/env python3
"""Run planned breaks in a scratch repo and guard code recording while the session is open.

Usage:
  break_session.py worktree REPO PATH COMMIT [--branch NAME]
  break_session.py worktree --clear REPO
  break_session.py start REPO
  break_session.py run REPO "IDS: WHAT WAS BROKEN" -- CHECK COMMAND...
  break_session.py replay EVIDENCE_FILE -- CHECK COMMAND...
  break_session.py status
  break_session.py end REPO

--harness DIR picks the harness; it defaults to the one this script sits in, at scripts/framework/.

worktree makes a new linked git worktree of REPO at PATH, detached at COMMIT or on a new branch NAME, for a
run that tests other code than the developer's, such as a pull request. It refuses a PATH that already
exists, so it only ever marks a worktree it made. The ownership marker names this harness, REPO, and
COMMIT, and lives in the worktree's private Git folder, outside its files, so `git worktree remove` deletes
it with the worktree. Unless REPO's checkout holds the harness, whose copy in the new worktree then runs,
it also records PATH (with the locator's folder inside it) as this harness's checkout for REPO, in
verify-worktrees.json in the project's private Git folder: every command that finds REPO's checkout reads
it before harness.json's locator and prints a line naming it, and no fingerprint covers it. `worktree
--clear REPO` forgets it, and is refused while a break session is open there; run it before removing the
worktree.

start opens a session in one of two modes and prints which it took. When REPO's checkout resolves to a
worktree carrying a marker for this harness and REPO, the break happens in place: that worktree is the
copy, no new worktree is made, and Stop and Start don't run, since the app already runs that worktree;
start runs harness.json's doctor first and refuses unless it reports the app ready. In place needs no
uncommitted product code in the worktree and its commit's product code to match the marker's commit; a
marked worktree that fails one of these, or a marker in a repo's main worktree, is refused, never quietly
copied instead. Otherwise start makes a scratch git worktree of REPO at the commit under test, replays the
developer's staged, unstaged, and untracked changes into it, confirms its code_state.py fingerprint
matches the developer's checkout, and points the app at the copy: when harness.json's start is a command,
it runs Stop and then Start with {checkout:REPO} filled with the copy and every other repo's placeholder
with that repo's checkout. Start must name {checkout:REPO}; when Start is `none`, nothing runs and the
checks read the copy from VERIFY_CHECKOUT_<REPO>; when Start is `user`, only a person starts the app and a
break can't run. Either way, make the break as an uncommitted edit in the copy it prints.

Product code is every file outside the harness's own folder and the skill copies beside it, across the
copy's whole Git checkout. A break is an uncommitted change to product code; the harness's files never
count as one, in either mode, since an in-place copy holds the harness's own work in progress and a scratch
copy's harness files are not what the check runs.

run confirms the copy holds an edit and its HEAD hasn't moved, and in a scratch copy that the developer's
checkout still matches. It stops and starts the app again the same way when harness.json's reloads is
false, and runs the check from the project root with VERIFY_PLANNED_BREAK set. It snapshots product code
before the restart and after the check; when anything moved in between, it leaves the copy as it is,
renames the run's evidence to <time>.held so it never counts, holds the session so run and replay refuse
until end, and exits 1 naming what moved. Otherwise it saves the edit as <time>.patch beside the
<time>.json evidence the check wrote, outside the run folder so it can be committed with the record,
restores the copy, and confirms its product code matches the start, whether the check passed, failed, or
crashed. A scratch copy is restored with `git reset --hard`; an in-place copy only has its product paths
reset to the start, so the harness's uncommitted work there is kept. When vf.py run accepted the break
run, it appends one line per targeted sub-feature the break caught cleanly to evidence/breaks.jsonl, the
harness's record of what was broken and when; vf.py status reads the break's evidence itself, so nothing
is written in the feature file.

replay applies the patch saved beside EVIDENCE_FILE to the repo its planned_break names and runs it as
run does, aimed at the same sub-features, to re-prove a check after its code changes. The repo's
session must be open.

end refuses while the copy's HEAD differs from the session's commit, since a commit there may hold a break
or someone's work. It then marks the session ending. For a scratch copy it points the app back at the
developer's checkout (Stop, then Start with the developer's checkouts) and removes the copy; in place it
restores the copy, confirms it, restarts the app on it the same way unless reloads is true, and keeps the
worktree. It closes the session and reports whether the developer's checkout, in place the copy itself,
still has its starting fingerprint. Ending a repo with no session does nothing, so end is safe to repeat
after a crash.

A session covers REPO's whole Git checkout, so manifest repos in that checkout share it: run and end
take the repo start named, and a start for another of them while it is open is refused. While a
session is open, code_state.py refuses ordinary code recording on every repo in it, including --checkout
overrides. Only the harness that opened the session may run or end it, or record its scratch code.
Commands from harness.json run from the project root with each {checkout:<repo>} filled in, with
VERIFY_CHECKOUT_<REPO> set for every repo, and with VERIFY_BREAK_SESSION set so their own code_state.py
calls are not refused.

The commands must establish which code the app loaded through its doctor. Restoring files does not
restart an app or undo data changes. An interrupted session stays open until end succeeds. A check whose
vf.py run was killed outright keeps running in its own process group; start, run, and end stop it first,
SIGINT and then SIGKILL, from the group ID vf.py run left in the session's folder, and say so.

Exits 0 when the step finished, whatever the check's own outcome; 1 when a guard found a problem,
such as a session already open, a marked worktree that can't be used in place, no edit to run, the
developer's checkout changing, a file moving during the check, or no evidence written; 2 when it could
not run, with a STOPPED: line on stderr.
"""

import argparse
import datetime
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _load(name, filename):
    # Loaded by path so this runs under `python3 -I`, which leaves the script's own directory off sys.path.
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_state = _load("harness_code_state", "code_state.py")
validate = code_state.validate
StateError = code_state.StateError
code_identity = validate.code_identity
DIFF = ["--binary", "--no-ext-diff", "--no-textconv", "--full-index"]
BREAKS_LOG = Path("evidence") / "breaks.jsonl"
# Lives in a worktree's private Git folder, which `git worktree remove` deletes with it.
OWNER_MARKER = "verify-scratch-owner.json"


class GuardError(Exception):
    pass


def git_output(directory, *args, data=None, env=None):
    """Git's output for the command run in directory; StateError when it fails."""
    result = subprocess.run(["git", "-C", str(directory), *args], input=data, capture_output=True, env=env)
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        raise StateError(f"git {args[0]} failed in {directory}: {detail}")
    return result.stdout


def command_setting(harness, label):
    """A command from harness.json, or StateError when it is missing or blank."""
    value = validate.command(harness, label)
    if value is None:
        raise StateError(f"harness.json names no {label} command")
    return value


def reloads(harness):
    """Whether the app picks up an edit to its checkout without a restart, from harness.json's reloads flag."""
    value = validate.command(harness, "reloads")
    if not isinstance(value, bool):
        raise StateError("harness.json's commands.reloads must be true or false")
    return value


def session_checkouts(harness, session, scratch):
    """Every settings repo's checkout as the app should see it: inside the scratch worktree for the repos in the
    session's Git checkout when scratch is set, else the developer's."""
    top, worktree = Path(session["top"]), Path(session["worktree"])
    checkouts = {}
    for name, locator in code_state.listed_repos(harness).items():
        located = validate.repo_checkout(harness, name, locator)
        if not located:
            # A repo this machine lacks; Start naming its {checkout:<repo>} fails when filled, and a check that runs it stops.
            continue
        located = located.resolve()
        if scratch and located.is_relative_to(top):
            located = worktree / located.relative_to(top)
        checkouts[name] = located
    return checkouts


def run_command(harness, command, checkouts, repo):
    """Run a harness.json command from the project root with its {checkout:<repo>} placeholders filled; StateError when it fails."""
    try:
        text = validate.fill_checkouts(command, checkouts)
    except ValueError as error:
        raise StateError(f"harness.json: {error}") from error
    print(f"Running: {text}", flush=True)
    env = {**os.environ, "VERIFY_BREAK_SESSION": repo, **code_state.checkout_env(checkouts)}
    result = subprocess.run(text, shell=True, cwd=validate.project_root(harness), env=env)
    if result.returncode:
        raise StateError(f"`{text}` exited {result.returncode}")


def point_app(harness, session, repo, scratch):
    """Make the app load the scratch copy, or the developer's checkouts again: Stop, then Start with the
    checkouts filled in. Nothing runs when Start is `none`, since the checks then read VERIFY_CHECKOUT_<REPO>.
    In place the copy is the developer's checkout, so either way this restarts the app on the same worktree."""
    start = command_setting(harness, "start")
    if start.lower() in (validate.START_NONE, validate.START_USER):
        return
    checkouts = session_checkouts(harness, session, scratch)
    stop = command_setting(harness, "stop")
    if stop.lower() != "none":
        run_command(harness, stop, checkouts, repo)
    run_command(harness, start, checkouts, repo)


def locate(harness, repo):
    """The developer's checkout for REPO, which may be a folder inside a Git checkout, and that checkout's top."""
    repos = code_state.listed_repos(harness)
    if repo not in repos:
        raise StateError(f"harness.json lists no repo named {repo}")
    checkout = validate.repo_checkout(harness, repo, repos[repo])
    if not checkout:
        raise StateError(f"{repo}: no Git checkout at {validate.recorded_worktree(harness, repo) or repos[repo]}")
    return checkout.resolve(), Path(validate.git(checkout, "rev-parse", "--show-toplevel")).resolve()


def snapshot_tree(worktree, harness):
    """A Git tree of the worktree's files as they are now, staged or not, so two moments can be diffed."""
    index = Path(git_output(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
    with tempfile.TemporaryDirectory() as scratch_index:
        # A copy of the real index keeps its file timestamps, so git rehashes only files that changed.
        temp_index = Path(scratch_index) / "index"
        shutil.copyfile(index, temp_index)
        env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
        git_output(worktree, "add", "-A", "--", *validate.source_pathspec(worktree, harness), env=env)
        return git_output(worktree, "write-tree", env=env).decode().strip()


def copy_files(names, source, target):
    """Copy the named files from one tree to another, keeping symlinks as symlinks and creating folders as needed."""
    for name in names:
        origin, copy = source / name, target / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        if origin.is_symlink():
            os.symlink(os.readlink(origin), copy)
        else:
            shutil.copy2(origin, copy)


def product_diff(session, harness, before, after, *flags):
    """git diff between two snapshots of the copy, limited to product code."""
    worktree = Path(session["worktree"])
    return git_output(worktree, "diff", *flags, before, after, "--", *validate.source_pathspec(worktree, harness))


def edit_since_start(session, harness):
    """The product code the copy changed since the session started, as a binary diff; empty when none."""
    return product_diff(session, harness, session["start_tree"], snapshot_tree(Path(session["worktree"]), harness), *DIFF)


def moved_since(session, harness, snapshot):
    """What in the copy differs from snapshot: the product paths that changed, and its HEAD when it moved."""
    worktree = Path(session["worktree"])
    moved = product_diff(session, harness, snapshot, snapshot_tree(worktree, harness), "--name-only").decode().split("\n")
    moved = [name for name in moved if name]
    if validate.git(worktree, "rev-parse", "HEAD") != session["commit"]:
        moved.append("HEAD")
    return moved


def restore(session, folder, harness):
    """Put the copy back to the code under test. A scratch copy is reset to its commit and gets the
    developer's saved changes again; an in-place copy has only its product paths reset to the session's
    start, so the harness's files there, staged or not, are left alone."""
    worktree = Path(session["worktree"])
    if session["in_place"]:
        spec = validate.source_pathspec(worktree, harness)
        # Start required clean product code, so the start snapshot equals the index and HEAD on these paths and
        # every untracked product file is the break's. With uncommitted product code at start, restore couldn't
        # tell staged from unstaged from untracked and would hand back a different index.
        git_output(worktree, "clean", "-fdq", "--", *spec)
        git_output(worktree, "restore", f"--source={session['start_tree']}", "--staged", "--worktree", "--", *spec)
        return
    git_output(worktree, "reset", "-q", "--hard", session["commit"])
    git_output(worktree, "clean", "-fdq", "--", *validate.source_pathspec(worktree, harness))
    for name, flags in (("staged.patch", ["--index"]), ("unstaged.patch", [])):
        patch = (folder / name).read_bytes()
        if patch:
            git_output(worktree, "apply", "--binary", *flags, data=patch)
    copy_files(session["untracked"], folder / "untracked", worktree)


def require_restored(session, harness, then):
    """GuardError unless the copy's product code and HEAD are back where the session started them."""
    moved = moved_since(session, harness, session["start_tree"])
    if moved:
        raise GuardError(f"the copy at {session['scratch']} didn't return to its starting state ({', '.join(moved[:5])}); {then}")


def require_session_repo(session, repo):
    """GuardError unless the open session was started for repo; repos in one Git checkout share its one session."""
    owner = session["repo"]
    if owner != repo:
        raise GuardError(f"{repo} shares its Git checkout with {owner}, and the break session there is open for {owner}; "
                         f"name {owner} in `vf.py break` commands, or close it with `vf.py break end {owner}`")


def load_session(checkout, repo, harness):
    """This harness's open session on the repo and the folder it lives in; GuardError when none is open."""
    session = code_state.open_session(checkout)
    if not session:
        raise GuardError(f"no break session is open for {repo}; start one with `vf.py break start {repo}`")
    code_state.require_session_owner(session, harness)
    require_session_repo(session, repo)
    return session, code_state.session_folder(checkout)


def save_session(folder, session):
    """Replace the session file in one step, so a reader never sees a half-written one."""
    path = folder / "session.json"
    path.with_suffix(".tmp").write_text(json.dumps(session, indent=2))
    path.with_suffix(".tmp").replace(path)


def harness_identity(harness):
    """The harness as an ownership marker names it: its repo's shared Git folder and its path from that repo's top.

    A run that tests a pull request makes the worktree with the harness in the developer's checkout and then
    runs the harness copy inside the new worktree, so an absolute path would never match. Only the same
    harness of the same repo, run from any of its worktrees, has this identity, and only a worktree
    `worktree` made carries a marker at all."""
    top = validate.git(harness, "rev-parse", "--show-toplevel")
    common = validate.git(harness, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not top or not common:
        raise StateError(f"{harness} is not in a Git checkout, so no worktree can be marked as its own")
    return {"git": str(Path(common).resolve()), "path": harness.resolve().relative_to(Path(top).resolve()).as_posix()}


def git_dirs(top):
    """The checkout's private Git folder and the repo's shared one; the same folder in the main worktree."""
    found = git_output(top, "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir").decode().split("\n")
    return Path(found[0]).resolve(), Path(found[1]).resolve()


def make_worktree(harness, repo, path, commit, branch):
    """Make a new linked worktree of the repo for this harness's run, mark it as made by the framework, and, unless
    the repo holds the harness, record it as the harness's checkout for the repo."""
    located, top = locate(harness, repo)
    path = path.resolve()
    if path.exists() or path.is_symlink():
        raise GuardError(f"{path} already exists; `vf.py break worktree` marks only a worktree it adds itself, "
                         f"so name a new path")
    commit = git_output(top, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    git_output(top, "worktree", "add", "-q", *(["-b", branch] if branch else ["--detach"]), str(path), commit)
    marker = {"harness": harness_identity(harness), "repo": repo, "commit": commit}
    (git_dirs(path)[0] / OWNER_MARKER).write_text(json.dumps(marker, indent=2))
    print(f"Worktree for {repo} at {path}, on {branch or 'a detached HEAD'} at {commit[:12]}.")
    project_top = validate.git(validate.project_root(harness), "rev-parse", "--show-toplevel")
    if project_top and Path(project_top).resolve() == top:
        # The harness has a copy in the new worktree, and a run of that copy finds its own repo there.
        print(f"{repo} holds this harness, so run the harness copy in {path}, and make the other repos' worktrees "
              f"from it; `vf.py break start {repo}` there breaks it in place.")
        return 0
    checkout = path / located.relative_to(top)
    record_worktree(harness, repo, checkout)
    print(f"This harness now uses {checkout} as {repo}'s checkout, in place of harness.json's locator; point the app "
          f"at it, and `vf.py break start {repo}` then breaks it in place. `vf.py break worktree --clear {repo}` "
          f"goes back to the locator; run it before removing the worktree.")
    return 0


def write_worktrees(harness, update):
    """Apply update to the harness's {repo: path} entry in the project's recorded worktrees and save the file in one step."""
    path = validate.worktrees_file(harness)
    if path is None:
        raise StateError(f"{validate.project_root(harness)} is not in a Git checkout, so no worktree can be recorded for it")
    try:
        data = validate.recorded_worktrees(harness)
    except ValueError as error:
        raise StateError(str(error)) from error
    key = str(harness.resolve())
    entry = data.get(key) if isinstance(data.get(key), dict) else {}
    update(entry)
    if entry:
        data[key] = entry
    else:
        data.pop(key, None)
    if data:
        path.with_suffix(".tmp").write_text(json.dumps(data, indent=2) + "\n")
        path.with_suffix(".tmp").replace(path)
    else:
        path.unlink(missing_ok=True)


def record_worktree(harness, repo, checkout):
    """Record checkout as this harness's checkout for repo, read before harness.json's locator."""
    write_worktrees(harness, lambda entry: entry.update({repo: str(checkout)}))


def clear_worktree(harness, repo):
    """Forget the worktree `worktree` recorded for repo, so the harness uses harness.json's locator again."""
    if code_state.listed_repos(harness).get(repo) is None:
        raise StateError(f"harness.json lists no repo named {repo}")
    recorded = validate.recorded_worktree(harness, repo)
    if recorded is None:
        print(f"No worktree is recorded for {repo}; the harness uses harness.json's locator.")
        return 0
    checkout = recorded if validate.git(recorded, "rev-parse", "--show-toplevel") else None
    session = code_state.open_session(checkout) if checkout else None
    if session and not session["ending"]:
        raise GuardError(f"a break session is open on {recorded}; close it with `vf.py break end {session['repo']}` first")
    write_worktrees(harness, lambda entry: entry.pop(repo, None))
    print(f"{repo}: no longer uses {recorded}; the harness uses harness.json's locator again. The worktree itself is untouched.")
    return 0


def owner_marker(harness, repo, top):
    """The marker `worktree` left for this harness and repo in top's private Git folder, or None when top has
    no marker. GuardError for a marker it can't honor, so a marked worktree never quietly gets a copy instead."""
    private, common = git_dirs(top)
    path = private / OWNER_MARKER
    if not path.exists():
        return None
    if private == common:
        raise GuardError(f"{top} is {repo}'s main worktree, which holds the developer's own work, yet it carries a "
                         f"break worktree marker at {path}; remove the marker, or break in a worktree `vf.py break worktree` made")
    try:
        marker = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise GuardError(f"{top}'s break worktree marker at {path} can't be read ({error}); remove the worktree and make a new one")
    if not isinstance(marker, dict) or marker.get("harness") != harness_identity(harness) or marker.get("repo") != repo:
        raise GuardError(f"{top} was made by `vf.py break worktree` for another harness or repo than this harness's "
                         f"{repo}; run the break from that harness, or make a worktree for this one")
    return marker


def require_in_place(harness, repo, top, marker):
    """GuardError unless the marked worktree at top can host the break in place."""
    changed = validate.uncommitted_files(top, harness)
    if changed is None:
        raise StateError(f"git status failed in {top}")
    if changed:
        raise GuardError(f"{top} has uncommitted product code ({', '.join(changed[:5])}); an in-place break resets "
                         f"product code to where the session starts, so commit or remove those changes first")
    moved = git_output(top, "diff", "--name-only", marker["commit"], "HEAD", "--",
                       *validate.source_pathspec(top, harness)).decode().split("\n")
    moved = [name for name in moved if name]
    if moved:
        raise GuardError(f"{top}'s product code no longer matches {marker['commit'][:12]}, the commit `vf.py break worktree` "
                         f"made it at ({', '.join(moved[:5])}); make a new worktree at the code to test")


def require_app_ready(harness, repo, top):
    """GuardError unless the doctor reports the app ready, which in place means running the marked worktree,
    since nothing restarts the app before the first break when reloads is true."""
    vf = _load("harness_vf", "vf.py")
    try:
        doctor = vf.run_doctor(harness, validate, vf.checkout_env(harness, validate, code_state, None, "skip"))
    except vf.Stopped as stopped:
        raise StateError(str(stopped)) from stopped
    if not vf.ready(doctor):
        raise GuardError(f"{top} is a worktree `vf.py break worktree` made, so the break happens in place on the app "
                         f"already running it, but {vf.not_ready_message(doctor)}. Start the app on {top}, then run "
                         f"`vf.py break start {repo}` again")


def group_alive(group):
    """Whether any process is left in the process group."""
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_leftover_check(folder):
    """Stop a planned break's check that outlived the `vf.py run` that started it, such as one killed by a timeout:
    SIGINT to the process group the session folder records, as Ctrl-C would, then SIGKILL once the grace runs out."""
    path = folder / code_state.CHECK_GROUP
    try:
        group = int(path.read_text())
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return
    if group > 1 and group_alive(group):
        grace = _load("harness_vf", "vf.py").BREAK_STOP_GRACE
        how = "SIGINT"
        os.killpg(group, signal.SIGINT)
        deadline = time.monotonic() + grace
        while group_alive(group) and time.monotonic() < deadline:
            time.sleep(0.1)
        if group_alive(group):
            how = "SIGINT, then SIGKILL"
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        print(f"Stopped the check a killed `vf.py run` left running (process group {group}, with {how}) before going on.", flush=True)
    path.unlink(missing_ok=True)


def start(harness, repo):
    """Open a break session, in place in a marked worktree or in a new scratch worktree."""
    checkout, top = locate(harness, repo)
    session = code_state.open_session(checkout)
    if session:
        code_state.require_session_owner(session, harness)
        require_session_repo(session, repo)
        stop_leftover_check(code_state.session_folder(checkout))
        raise GuardError(f"a break session is already open for {repo}; see `vf.py break status`, or close it with `vf.py break end {repo}`")
    start_command = command_setting(harness, "start")
    reloads(harness)
    if start_command.lower() == validate.START_USER:
        raise StateError("harness.json says only a person starts the app (start: user), so a planned break can't run here; record the proof as Not break-tested")
    marker = owner_marker(harness, repo, top)
    in_place = marker is not None
    if in_place:
        require_in_place(harness, repo, top, marker)
        require_app_ready(harness, repo, top)
        # The worktree is both the code under test and the copy, so the session's checkout is the copy itself.
        worktree, scratch = top, checkout
    else:
        worktree = Path(tempfile.mkdtemp(prefix=f"verify-break-{repo}-")).resolve()
        scratch = worktree / checkout.relative_to(top)
    under_test = code_state.checkout_state(checkout, harness)

    folder = code_state.session_folder(checkout)
    # Left by a start that crashed before writing its session file, so nothing else refers to it.
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir()
    untracked = []
    if not in_place:
        spec = validate.source_pathspec(top, harness)
        (folder / "staged.patch").write_bytes(git_output(top, "diff", "--cached", *DIFF, "--", *spec))
        (folder / "unstaged.patch").write_bytes(git_output(top, "diff", *DIFF, "--", *spec))
        listing = git_output(top, "ls-files", "--others", "--exclude-standard", "-z", "--", *spec)
        untracked = sorted(os.fsdecode(name) for name in listing.split(b"\0") if name)
        copy_files(untracked, top, folder / "untracked")

    session = {
        "harness": str(harness.resolve()),
        "repo": repo, "checkout": str(checkout), "top": str(top), "worktree": str(worktree), "scratch": str(scratch),
        "commit": under_test["commit"], "dirty_hash": under_test["dirty_hash"], "untracked": untracked,
        "in_place": in_place,
        # end sets ending before it points the app back or restarts it; held names why run must wait for end.
        "ending": False, "held": None,
    }
    # Written before the worktree exists, so a crash from here on leaves a session that blocks ordinary runs and that end can clean up.
    save_session(folder, session)
    if not in_place:
        git_output(top, "worktree", "add", "-q", "--detach", str(worktree), under_test["commit"])
        restore(session, folder, harness)
        if code_identity(code_state.checkout_state(scratch, harness)) != code_identity(under_test):
            raise GuardError(f"the scratch copy at {scratch} doesn't match {checkout}'s code after replaying its changes; run `vf.py break end {repo}`")
    session["start_tree"] = snapshot_tree(worktree, harness)
    save_session(folder, session)

    if in_place:
        print(f"Break session open for {repo} in place: {scratch} is a worktree `vf.py break worktree` made, and the "
              f"doctor reports the app ready on it, so nothing was restarted.")
    else:
        print(f"Break session open for {repo} in a new scratch worktree at {worktree}.")
        point_app(harness, session, repo, scratch=True)
    print(f"Make the break as an uncommitted edit in {scratch}, then run:")
    print(f'  vf.py break run {repo} "<sub-feature IDs>: <what was broken>" -- <check command>')
    return 0


def evidence_files(harness):
    """Every evidence file in the harness now, so the ones a check writes can be told apart."""
    return set((harness / "evidence").glob("*/*.json"))


def planned_break_runs(paths):
    """The evidence files among paths that record a planned break run, in path order."""
    found = []
    for path in sorted(paths):
        record = validate.read_record(path)
        if record and record.get("planned_break"):
            found.append(path)
    return found


def run_break(harness, repo, planned, command, patch=None):
    """Run the check against the copy's edit, or against a saved patch, then restore the copy.
    Saves the edit as <time>.patch beside the evidence the check wrote and logs what the break caught."""
    ids, sep, what = planned.partition(": ")
    if not sep or not ids.strip() or not what.strip():
        raise StateError(f"expected \"<sub-feature IDs>: <what was broken>\", got {planned!r}")
    located, _ = locate(harness, repo)
    session, folder = load_session(located, repo, harness)
    stop_leftover_check(folder)
    if session["ending"]:
        raise GuardError(f"the session for {repo} is ending; finish it with `vf.py break end {repo}`")
    if session["held"]:
        raise GuardError(f"the session for {repo} is held: {session['held']}")
    # The session's own record, since pointing the app may rewrite the locator to name the scratch copy.
    checkout = Path(session["checkout"])
    worktree = Path(session["worktree"])
    # In place the checkout is the copy, which holds the break, so only a scratch copy has a separate original to watch.
    if not session["in_place"] and code_identity(code_state.checkout_state(checkout, harness)) != code_identity(session):
        raise GuardError(
            f"{checkout} changed since the session started, so the scratch copy no longer holds the code under test. "
            f"End the session and start a new one; if the change was a break made in the wrong place, undo it first"
        )
    if validate.git(worktree, "rev-parse", "HEAD") != session["commit"]:
        raise GuardError(f"a commit was made in {worktree}; a break must be an uncommitted edit. Move HEAD back to "
                         f"{session['commit'][:12]} once anything in the commit is saved, then run `vf.py break end {repo}`")
    if patch is not None:
        if edit_since_start(session, harness):
            raise GuardError(f"{session['scratch']} already holds an edit; replay applies its break to a clean copy")
        git_output(worktree, "apply", "--binary", data=patch)
    before = snapshot_tree(worktree, harness)
    edit = product_diff(session, harness, session["start_tree"], before, *DIFF)
    if not edit:
        raise GuardError(f"{session['scratch']} holds no edit; make the break there first")

    project = validate.project_root(harness)
    before_evidence = evidence_files(harness)
    runs, target = [], folder / "last-break.patch"
    try:
        if not reloads(harness):
            point_app(harness, session, repo, scratch=True)
        print(f"Running the check with VERIFY_PLANNED_BREAK={planned}", flush=True)
        exit_code = subprocess.run(command, cwd=project, env={**os.environ, "VERIFY_PLANNED_BREAK": planned}).returncode
        runs = planned_break_runs(evidence_files(harness) - before_evidence)
        if len(runs) == 1:
            target = runs[0].with_suffix(".patch")
        target.write_bytes(edit)
    finally:
        moved = moved_since(session, harness, before)
        if moved:
            # Restoring would erase what moved, and the check didn't run on the break alone, so its
            # evidence is renamed out of what validate reads: it must never count as a break.
            held = planned_break_runs(evidence_files(harness) - before_evidence)
            for path in held:
                path.rename(path.with_suffix(".held"))
            if held:
                # vf.py run already wrote status.md and recordings.html from that evidence; rebuild both without it.
                vf = _load("harness_vf", "vf.py")
                for line in vf.refresh_status(harness, validate):
                    print(line, file=sys.stderr)
                if failure := vf.build_pages("--recordings", str(harness)):
                    print(f"recordings.html was not rebuilt: {failure}", file=sys.stderr)
            session["held"] = (f"{', '.join(moved[:5])} changed in {worktree} while the app restarted or the check ran, "
                               f"so the copy was left as it is. Save anything there you need, then run `vf.py break end {repo}`, "
                               f"which resets the copy's product code")
            save_session(folder, session)
            raise GuardError(f"The break run is not usable: {session['held']}")
        restore(session, folder, harness)
        try:
            require_restored(session, harness, f"fix it there, then run `vf.py break end {repo}`")
        except GuardError as error:
            session["held"] = str(error)
            save_session(folder, session)
            raise

    print(f"Check exited {exit_code}. The copy is back at its starting state.")
    if len(runs) != 1:
        found = ", ".join(str(path) for path in runs) or "none"
        raise GuardError(f"expected the check to write one planned break evidence file, found {found}; the break is saved at {target}")
    print(f"Evidence: {runs[0]}")
    print(f"Break saved: {target}")
    for line in record_breaks(harness, runs[0]):
        print(line)
    return 0


def record_breaks(harness, evidence):
    """Append one line to evidence/breaks.jsonl for each sub-feature the accepted break run caught.

    A sub-feature counts as caught when a step judging it failed cleanly, as validate.break_catch decides.
    The log is the harness's plain record of what was broken and when, for a reader without the run folders;
    vf.py status credits the break from the evidence itself. Returns one line per targeted sub-feature saying
    whether it was caught.
    """
    record = validate.read_record(evidence)
    if not record or record.get("accepted_by") != validate.ACCEPTED_BY:
        return ["No break recorded: vf.py run did not accept the break run"]
    if record.get("stopped") is not None:
        return [f"No break recorded: the break run stopped ({record['stopped']}); run the break again"]
    if record.get("passed") is not False:
        return ["No break recorded: the break run did not fail"]
    cite = evidence.relative_to(harness).as_posix()
    what = record["planned_break"]["what"]
    at = record.get("finished_at") or datetime.datetime.now(datetime.timezone.utc).strftime(validate.TIME_FORMAT)
    lines, entries = [], []
    for sub_id in record["planned_break"]["sub_features"]:
        failed_steps, spoiled_by = validate.break_catch(record, sub_id)
        if not failed_steps:
            lines.append(f"{sub_id}: no step judging it failed, so the break proves nothing for it; plan a break that reaches its own step")
            continue
        if spoiled_by is not None:
            lines.append(f"{sub_id}: step '{spoiled_by}' failed before any step judging it, so the break proves nothing for it; "
                         "plan a break of its own that the earlier steps pass through")
            continue
        entries.append({"at": at, "sub_feature": sub_id, "check": record["check"], "what": what, "step": failed_steps[0], "evidence": cite})
        lines.append(f"Break recorded for {sub_id}: step '{failed_steps[0]}' caught it")
    if entries:
        log = harness / BREAKS_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as handle:
            handle.writelines(json.dumps(entry) + "\n" for entry in entries)
    return lines


def replay(harness, evidence, command):
    """Run a saved break again: apply the patch beside the evidence to the repo it edited and run the check as run does."""
    record = validate.read_record(evidence)
    planned_break = (record or {}).get("planned_break")
    if not planned_break:
        raise StateError(f"{evidence} is not a planned break run")
    if not planned_break.get("repo"):
        raise StateError(f"{evidence} doesn't name the repo its break edited; run the break again with `vf.py break run`")
    patch = evidence.with_suffix(".patch")
    if not patch.is_file():
        raise StateError(f"{evidence} has no saved break at {patch}")
    planned = f"{','.join(planned_break['sub_features'])}: {planned_break['what']}"
    return run_break(harness, planned_break["repo"], planned, command, patch.read_bytes())


def status(harness):
    """Print one line per repo saying whether a break session is open on it and what state the copy is in."""
    for repo, locator in code_state.listed_repos(harness).items():
        checkout = validate.repo_checkout(harness, repo, locator)
        session = code_state.open_session(checkout) if checkout else None
        if not session:
            print(f"{repo}: no break session")
            continue
        if Path(session["harness"]) != harness.resolve():
            print(f"{repo}: break session belongs to {session['harness']}; close it there before running this harness")
            continue
        worktree = Path(session["worktree"])
        if session["ending"]:
            state = "ending; run end again to finish"
        elif not worktree.is_dir() or "start_tree" not in session:
            state = "not fully started; run end to clean up"
        elif session["held"]:
            state = f"held: {session['held']}"
        elif not edit_since_start(session, harness):
            state = "at its starting state"
        else:
            state = "holds an edit"
        shared = f" for {session['repo']}" if session["repo"] != repo else ""
        place = " in place" if session["in_place"] else ""
        print(f"{repo}: break session{shared} open{place} on {session['scratch']}, {state}")
    return 0


def end(harness, repo):
    """Close the session and report whether the developer's checkout changed while it was open. A scratch copy
    is removed after the app is pointed back; an in-place copy is restored, the app restarted on it, and kept."""
    located, _ = locate(harness, repo)
    session = code_state.open_session(located)
    if not session:
        print(f"No break session is open for {repo}.")
        return 0
    code_state.require_session_owner(session, harness)
    require_session_repo(session, repo)
    folder = code_state.session_folder(located)
    stop_leftover_check(folder)
    checkout, top = Path(session["checkout"]), Path(session["top"])
    worktree = Path(session["worktree"])
    if not session["in_place"] and worktree.resolve() == top:
        raise StateError(f"the session names {top}, the developer's checkout, as its scratch copy; remove {folder} by hand after checking it")
    started = worktree.is_dir() and "start_tree" in session
    head = validate.git(worktree, "rev-parse", "HEAD") if started else session["commit"]
    if head != session["commit"]:
        raise GuardError(f"{worktree}'s HEAD moved from {session['commit'][:12]} to {(head or 'nothing')[:12]} during the session, "
                         f"and a commit there may hold a break or someone's work. Move HEAD back to {session['commit'][:12]} "
                         f"once anything in it is saved, then run `vf.py break end {repo}` again")

    # Marked before pointing back or restarting, so those commands' own code-state calls record the checkout the
    # app is getting, break runs are refused, and a crash leaves a session end can finish.
    session["ending"] = True
    save_session(folder, session)
    if session["in_place"]:
        if started:
            restore(session, folder, harness)
            require_restored(session, harness, f"fix it there, then run `vf.py break end {repo}` again")
            # The app still runs the last break's code unless it reloads the restored files by itself.
            if not reloads(harness):
                point_app(harness, session, repo, scratch=False)
    else:
        point_app(harness, session, repo, scratch=False)
        if worktree.exists():
            git_output(top, "worktree", "remove", "--force", str(worktree))
        git_output(top, "worktree", "prune")
    shutil.rmtree(folder)

    if code_identity(code_state.checkout_state(checkout, harness)) != code_identity(session):
        changed = validate.uncommitted_files(checkout, harness) or []
        listed = ", ".join(changed[:5]) or "the commit"
        raise GuardError(
            f"Break session for {repo} closed, but {checkout} changed while it was open ({listed}). "
            f"Check that no break was made there"
        )
    if session["in_place"]:
        print(f"Break session for {repo} closed; {checkout} is back at its starting state, the app runs it again, and it stays in place.")
    else:
        print(f"Break session for {repo} closed; the app is pointed back at {checkout}, which is unchanged.")
    return 0


def main():
    argv = sys.argv[1:]
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", type=Path, default=Path(__file__).resolve().parents[2])
    actions = parser.add_subparsers(dest="action", required=True)
    worktree = actions.add_parser("worktree")
    worktree.add_argument("repo")
    worktree.add_argument("path", type=Path, nargs="?")
    worktree.add_argument("commit", nargs="?")
    worktree.add_argument("--branch", help="make the worktree on this new branch instead of a detached HEAD")
    worktree.add_argument("--clear", action="store_true",
                          help="forget the worktree recorded for REPO, so the harness uses harness.json's locator again")
    actions.add_parser("start").add_argument("repo")
    run = actions.add_parser("run")
    run.add_argument("repo")
    run.add_argument("planned_break", metavar='"IDS: WHAT WAS BROKEN"')
    actions.add_parser("replay").add_argument("evidence", type=Path)
    actions.add_parser("status")
    actions.add_parser("end").add_argument("repo")
    args = parser.parse_args(argv)
    if args.action in ("run", "replay") and not command:
        parser.error(f"{args.action} needs the check command after --")
    if args.action == "worktree" and (args.clear != (args.path is None) or args.clear != (args.commit is None)
                                      or (args.clear and args.branch)):
        parser.error("worktree takes REPO PATH COMMIT [--branch NAME], or --clear REPO")
    harness = args.harness.resolve()
    try:
        if args.action == "worktree" and args.clear:
            return clear_worktree(harness, args.repo)
        if args.action == "worktree":
            return make_worktree(harness, args.repo, args.path, args.commit, args.branch)
        if args.action == "start":
            return start(harness, args.repo)
        if args.action == "run":
            return run_break(harness, args.repo, args.planned_break, command)
        if args.action == "replay":
            return replay(harness, args.evidence.resolve(), command)
        if args.action == "status":
            return status(harness)
        return end(harness, args.repo)
    except GuardError as error:
        print(error, file=sys.stderr)
        return 1
    except StateError as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
