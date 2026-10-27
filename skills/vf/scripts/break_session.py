#!/usr/bin/env python3
"""Run planned breaks in a scratch repo and guard code recording while the session is open.

Usage:
  break_session.py start REPO
  break_session.py run REPO "IDS: WHAT WAS BROKEN" -- CHECK COMMAND...
  break_session.py replay EVIDENCE_FILE -- CHECK COMMAND...
  break_session.py status
  break_session.py end REPO

--harness DIR picks the harness; it defaults to the one this script sits in, at scripts/framework/.

start makes a scratch git worktree of REPO at the commit under test, replays the developer's staged,
unstaged, and untracked changes into it, and confirms its code_state.py fingerprint matches the
developer's checkout. It then opens a session and points the app at the copy: when settings.md's
Start is a command, it runs Stop and then Start with {checkout:REPO} filled with the copy and every
other repo's placeholder with that repo's checkout. Start must name {checkout:REPO}; when Start is
`none`, nothing runs and the checks read the copy from VERIFY_CHECKOUT_<REPO>; when Start is `user`,
only a person starts the app and a break can't run. Make the break as an uncommitted edit in the copy it prints.

run confirms the developer's checkout still matches and the copy holds an edit, stops and starts the
app again the same way when settings.md's Reloads is `no`, and runs the check from the project root with
VERIFY_PLANNED_BREAK set. It saves the edit as <time>.patch beside the <time>.json evidence the check
wrote, outside the run folder so it can be committed with the record, then restores the copy to its starting state and confirms its fingerprint, whether the check
passed, failed, or crashed. When vf.py run accepted the break run, it appends one line per targeted
sub-feature whose judging step failed to evidence/breaks.jsonl, the harness's record of what was broken
and when; vf.py status reads the break's evidence itself, so nothing is written in the feature file.

replay applies the patch saved beside EVIDENCE_FILE to the repo its planned_break names and runs it as
run does, aimed at the same sub-features, to re-prove a check after its code changes. The repo's
session must be open.

end points the app back at the developer's checkout (Stop, then Start with the developer's checkouts), removes the copy, closes the session, and
reports whether the developer's checkout still has its starting fingerprint. Ending a repo with no
session does nothing, so end is safe to repeat after a crash.

A session copies REPO's whole Git checkout, so settings repos in that checkout share it: run and end
take the repo start named, and a start for another of them while it is open is refused. While a
session is open, code_state.py refuses ordinary code recording on every repo in it, including --checkout
overrides. Only the harness that opened the session may run or end it, or record its scratch code.
Commands from settings.md run from the project root with each {checkout:<repo>} filled in, with
VERIFY_CHECKOUT_<REPO> set for every repo, and with VERIFY_BREAK_SESSION set so their own code_state.py
calls are not refused.

The commands must establish which code the app loaded through its doctor. Restoring files does not
restart an app or undo data changes. An interrupted session stays open until end succeeds.

Exits 0 when the step finished, whatever the check's own outcome; 1 when a guard found a problem,
such as a session already open, no edit to run, the developer's checkout changing, or no evidence
written; 2 when it could not run, with a STOPPED: line on stderr.
"""

import argparse
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
    """A '## Commands' value from settings.md, or StateError when the line is missing."""
    value = validate.setting(harness, "Commands", label)
    if value is None:
        raise StateError(f"settings.md has no '- {label}:' line under '## Commands'")
    return value


def reloads(harness):
    """Whether the app picks up an edit to its checkout without a restart, from settings.md's Reloads line."""
    value = command_setting(harness, "Reloads").lower()
    if value not in validate.RELOADS:
        raise StateError(f"settings.md's Reloads must be yes or no, not {value}")
    return value == "yes"


def session_checkouts(harness, session, scratch):
    """Every settings repo's checkout as the app should see it: inside the scratch worktree for the repos in the
    session's Git checkout when scratch is set, else the developer's."""
    project = validate.project_root(harness)
    top, worktree = Path(session["top"]), Path(session["worktree"])
    checkouts = {}
    for name, locator in code_state.listed_repos(harness).items():
        located = validate.resolve_repo(locator, project)
        if not located:
            raise StateError(f"{name}: no Git checkout at {locator}")
        located = located.resolve()
        if scratch and located.is_relative_to(top):
            located = worktree / located.relative_to(top)
        checkouts[name] = located
    return checkouts


def run_command(harness, command, checkouts, repo):
    """Run a settings.md command from the project root with its {checkout:<repo>} placeholders filled; StateError when it fails."""
    try:
        text = validate.fill_checkouts(command, checkouts)
    except ValueError as error:
        raise StateError(f"settings.md: {error}") from error
    print(f"Running: {text}", flush=True)
    env = {**os.environ, "VERIFY_BREAK_SESSION": repo, **code_state.checkout_env(checkouts)}
    result = subprocess.run(text, shell=True, cwd=validate.project_root(harness), env=env)
    if result.returncode:
        raise StateError(f"`{text}` exited {result.returncode}")


def point_app(harness, session, repo, scratch):
    """Make the app load the scratch copy, or the developer's checkouts again: Stop, then Start with the
    checkouts filled in. Nothing runs when Start is `none`, since the checks then read VERIFY_CHECKOUT_<REPO>."""
    start = command_setting(harness, "Start")
    if start.lower() in (validate.START_NONE, validate.START_USER):
        return
    checkouts = session_checkouts(harness, session, scratch)
    stop = command_setting(harness, "Stop")
    if stop.lower() != "none":
        run_command(harness, stop, checkouts, repo)
    run_command(harness, start, checkouts, repo)


def locate(harness, repo):
    """The developer's checkout for REPO, which may be a folder inside a Git checkout, and that checkout's top."""
    repos = code_state.listed_repos(harness)
    if repo not in repos:
        raise StateError(f"settings.md lists no repo named {repo}")
    checkout = validate.resolve_repo(repos[repo], validate.project_root(harness))
    if not checkout:
        raise StateError(f"{repo}: no Git checkout at {repos[repo]}")
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


def restore(session, folder, harness):
    """Put the scratch copy back to the code under test: its commit plus the developer's saved changes."""
    worktree = Path(session["worktree"])
    git_output(worktree, "reset", "-q", "--hard", session["commit"])
    git_output(worktree, "clean", "-fdq", "--", *validate.source_pathspec(worktree, harness))
    for name, flags in (("staged.patch", ["--index"]), ("unstaged.patch", [])):
        patch = (folder / name).read_bytes()
        if patch:
            git_output(worktree, "apply", "--binary", *flags, data=patch)
    copy_files(session["untracked"], folder / "untracked", worktree)


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


def start(harness, repo):
    """Open a break session: save the developer's changes, make the scratch worktree, and point the app at it."""
    checkout, top = locate(harness, repo)
    session = code_state.open_session(checkout)
    if session:
        code_state.require_session_owner(session, harness)
        require_session_repo(session, repo)
        raise GuardError(f"a break session is already open for {repo}; see `vf.py break status`, or close it with `vf.py break end {repo}`")
    start_command = command_setting(harness, "Start")
    reloads(harness)
    if start_command.lower() == validate.START_USER:
        raise StateError("settings.md says only a person starts the app (Start: user), so a planned break can't run here; record the proof as Not break-tested")
    under_test = code_state.checkout_state(checkout, harness)

    folder = code_state.session_folder(checkout)
    # Left by a start that crashed before writing its session file, so nothing else refers to it.
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir()
    spec = validate.source_pathspec(top, harness)
    (folder / "staged.patch").write_bytes(git_output(top, "diff", "--cached", *DIFF, "--", *spec))
    (folder / "unstaged.patch").write_bytes(git_output(top, "diff", *DIFF, "--", *spec))
    listing = git_output(top, "ls-files", "--others", "--exclude-standard", "-z", "--", *spec)
    untracked = sorted(os.fsdecode(name) for name in listing.split(b"\0") if name)
    copy_files(untracked, top, folder / "untracked")

    worktree = Path(tempfile.mkdtemp(prefix=f"verify-break-{repo}-")).resolve()
    scratch = worktree / checkout.relative_to(top)
    session = {
        "harness": str(harness.resolve()),
        "repo": repo, "checkout": str(checkout), "top": str(top), "worktree": str(worktree), "scratch": str(scratch),
        "commit": under_test["commit"], "dirty_hash": under_test["dirty_hash"], "untracked": untracked,
        "app_checkout": str(scratch),
    }
    # Written before the worktree exists, so a crash from here on leaves a session that blocks ordinary runs and that end can clean up.
    save_session(folder, session)
    git_output(top, "worktree", "add", "-q", "--detach", str(worktree), under_test["commit"])
    restore(session, folder, harness)
    copied = code_state.checkout_state(scratch, harness)
    if code_identity(copied) != code_identity(under_test):
        raise GuardError(f"the scratch copy at {scratch} doesn't match {checkout}'s code after replaying its changes; run `vf.py break end {repo}`")
    session["start_tree"] = snapshot_tree(worktree, harness)
    save_session(folder, session)

    point_app(harness, session, repo, scratch=True)
    print(f"Break session open for {repo}. Make the break as an uncommitted edit in {scratch}, then run:")
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
    """Run the check against the scratch copy's edit, or against a saved patch, then restore the copy.
    Saves the edit as <time>.patch beside the evidence the check wrote and logs what the break caught."""
    ids, sep, what = planned.partition(": ")
    if not sep or not ids.strip() or not what.strip():
        raise StateError(f"expected \"<sub-feature IDs>: <what was broken>\", got {planned!r}")
    located, _ = locate(harness, repo)
    session, folder = load_session(located, repo, harness)
    # The session's own record, since pointing the app may rewrite the locator to name the scratch copy.
    checkout = Path(session["checkout"])
    if session["app_checkout"] != session["scratch"]:
        raise GuardError(f"the session for {repo} is ending; finish it with `vf.py break end {repo}`")
    worktree = Path(session["worktree"])
    if code_identity(code_state.checkout_state(checkout, harness)) != code_identity(session):
        raise GuardError(
            f"{checkout} changed since the session started, so the scratch copy no longer holds the code under test. "
            f"End the session and start a new one; if the change was a break made in the wrong place, undo it first"
        )
    if validate.git(worktree, "rev-parse", "HEAD") != session["commit"]:
        raise GuardError(f"a commit was made in {worktree}; a break must be an uncommitted edit. Run `vf.py break end {repo}` and start again")
    if patch is not None:
        if snapshot_tree(worktree, harness) != session["start_tree"]:
            raise GuardError(f"{session['scratch']} already holds an edit; replay applies its break to a clean copy")
        git_output(worktree, "apply", "--binary", data=patch)
    edit = git_output(worktree, "diff", *DIFF, session["start_tree"], snapshot_tree(worktree, harness))
    if not edit:
        raise GuardError(f"{session['scratch']} holds no edit; make the break there first")

    project = validate.project_root(harness)
    before = evidence_files(harness)
    try:
        if not reloads(harness):
            point_app(harness, session, repo, scratch=True)
        print(f"Running the check with VERIFY_PLANNED_BREAK={planned}", flush=True)
        exit_code = subprocess.run(command, cwd=project, env={**os.environ, "VERIFY_PLANNED_BREAK": planned}).returncode
        runs = planned_break_runs(evidence_files(harness) - before)
        target = runs[0].with_suffix(".patch") if len(runs) == 1 else folder / "last-break.patch"
        target.write_bytes(edit)
    finally:
        restore(session, folder, harness)
        if code_identity(code_state.checkout_state(Path(session["scratch"]), harness)) != code_identity(session):
            raise GuardError(f"the scratch copy at {session['scratch']} didn't return to its starting state; run `vf.py break end {repo}`")

    print(f"Check exited {exit_code}. The scratch copy is back at its starting state.")
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

    A sub-feature counts as caught when a step judging it failed. The log is the harness's plain record of
    what was broken and when, for a reader without the run folders; vf.py status credits the break from the
    evidence itself. Returns one line per targeted sub-feature saying whether it was caught.
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
        failed_steps = [step["name"] for step in validate.steps_judging(record, sub_id) if step.get("passed") is False]
        if not failed_steps:
            lines.append(f"{sub_id}: no step judging it failed, so the break proves nothing for it; plan a break that reaches its own step")
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
    """Print one line per repo saying whether a break session is open on it and what state the scratch copy is in."""
    project = validate.project_root(harness)
    for repo, locator in code_state.listed_repos(harness).items():
        checkout = validate.resolve_repo(locator, project)
        session = code_state.open_session(checkout) if checkout else None
        if not session:
            print(f"{repo}: no break session")
            continue
        if Path(session["harness"]) != harness.resolve():
            print(f"{repo}: break session belongs to {session['harness']}; close it there before running this harness")
            continue
        worktree = Path(session["worktree"])
        if session["app_checkout"] != session["scratch"]:
            state = "ending; run end again to finish"
        elif not worktree.is_dir() or "start_tree" not in session:
            state = "not fully started; run end to clean up"
        elif snapshot_tree(worktree, harness) == session["start_tree"]:
            state = "at its starting state"
        else:
            state = "holds an edit"
        shared = f" for {session['repo']}" if session["repo"] != repo else ""
        print(f"{repo}: break session{shared} open on {session['scratch']}, {state}")
    return 0


def end(harness, repo):
    """Close the session: point the app back at the developer's checkout, remove the scratch worktree, and
    report whether the developer's checkout changed while the session was open."""
    located, _ = locate(harness, repo)
    session = code_state.open_session(located)
    if not session:
        print(f"No break session is open for {repo}.")
        return 0
    code_state.require_session_owner(session, harness)
    require_session_repo(session, repo)
    folder = code_state.session_folder(located)
    checkout, top = Path(session["checkout"]), Path(session["top"])
    worktree = Path(session["worktree"])
    if worktree.resolve() == top:
        raise StateError(f"the session names {top}, the developer's checkout, as its scratch copy; remove {folder} by hand after checking it")

    # Marked before pointing back, so the point-back command records the developer's checkout and a crash leaves the session open.
    session["app_checkout"] = session["checkout"]
    save_session(folder, session)
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
    harness = args.harness.resolve()
    try:
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
