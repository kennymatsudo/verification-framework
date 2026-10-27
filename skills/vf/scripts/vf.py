#!/usr/bin/env python3
"""The verification framework's command-line tool.

Usage: vf.py COMMAND [ARGS ...]

validate, code-state, break, replay, and clip run the framework script of that
name beside this one with ARGS, and exit with its exit code; each one's --help
describes it. start, stop, and doctor run launch.py's command of that name: an
optional launcher that records the code on disk when it starts the app, so a
doctor can compare it with the checkout under test. Run from a harness's
scripts/framework/, they act on that harness.

vf.py run -- CHECK COMMAND... runs a check from the project root and writes its evidence file from the
events the check reports. First it runs settings.md's Doctor command and refuses to run the check unless
the doctor exits 0, so no evidence is ever recorded against an app that was not ready or was running
other code. The doctor's exit code and output go in the record as `doctor`.

It gives the doctor and the check one VERIFY_CHECKOUT_<REPO> variable per repo in settings.md, naming the
checkout the run records for that repo (the scratch copy during a planned break), so a check that runs
the code itself runs it from there. It gives the check two more: VERIFY_REPORT, a file the check appends
one JSON object per line to, and VERIFY_RUN_DIR, the folder for its video, screenshots, and logs. The events are check
(name, reads, and optionally sub_features), step (name, passed, at, and optionally sub_features, detail,
evidence, snapshot), mark (kind, label, at), recording (video, starts_at), created (lists of IDs by
kind), and stopped (reason). The check event may come anywhere in the report; one written first still
names the check if the run is killed. A check that reports no sub_features covers the ones its steps
name, plus, when it judged none or stopped, the ones the feature map proves with this exact command,
so a run that stops before judging what it was run for is recorded as stopped rather than refused.

vf.py run records started_at and finished_at and the code code_state.py reports for the repos the run needs
(those the proof lines of the behaviors this command proves name with `Repos: a, b.`, else every repo in
settings.md), which must not change while the check runs, VERIFY_PLANNED_BREAK as planned_break with the repo of the break session this
harness has open (the repo `break start` named, when several repos share its Git checkout), and the
verdict from the exit code: 0 passed, 1 a step failed, anything else stopped.
With VERIFY_PLANNED_BREAK set and no session open, or sessions open on several checkouts, it stops before
running the check. It also records `harness_code`, a SHA-256 (line endings
normalized) of settings.md, of every file under the harness's scripts/ apart from scripts/framework/ and
other checks' entries under scripts/checks/, and of any file the check command names, so a planned break
and a later pass can be shown to have run the same check. It accepts the record under
evidence/<check>/<time>.json only when the events follow the Evidence rules and agree with the exit
code, stamps it "accepted_by": "vf.py run", builds its replay page, refreshes status.md, and exits with
the check's code. Otherwise it writes the record as <time>.json.refused, so no result can cite it,
prints each reason on a REFUSED: line, and exits 2. A break session's check runs through it:
vf.py break run REPO "IDS: WHAT" -- python3 scripts/framework/vf.py run -- CHECK COMMAND...

vf.py verify ID [ID ...] [--start] runs the proof of each named sub-feature: it looks up each one's
check command in the feature map, runs every distinct command once through vf.py run, which runs the
doctor first, then prints each named sub-feature's line from status.md. --start runs settings.md's Start
command, with each {checkout:<repo>} filled with that repo's checkout, when the doctor says the app is not
ready, then waits for the doctor to report ready; a Start of `user` means only a person starts the app, so
it stops and says so. Exits 0 when every named sub-feature is
Verified, 1 when any is not, and 2 when a check could not run, such as when the doctor reports not ready.

vf.py status computes every mapped behavior's verdict from the feature map, the accepted evidence,
and the Not verified records, writes them as status.md's Latest results, and prints them. Nobody
writes a Verified line by hand: validate.py fails one that status would not write now. It renders
what the evidence on this machine supports, so run it where the evidence is. Exits 1 when the
feature map has errors, and writes nothing then.

vf.py not-verified ID "REASON" [--until-break] records that ID's check could not run or its pass
cannot be trusted, in evidence/not-verified.jsonl, and refreshes status.md. The record stands until
a later accepted run of a check covering ID; with --until-break, until a later planned break aimed
at ID as well, for a check whose steps changed.

vf.py sync HARNESS_DIR [--restore] creates or updates a harness's framework copies: rules.md,
every script in FRAMEWORK_SCRIPTS under scripts/framework/, and the vf, vf-verify, and
vf-explain skills beside the harness, without their scripts/, so a clone of the repo holds
everything the skills need and each script is pinned once. When the project root has more
than one skills directory, each one gets the skill copies. Run it from the installed vf
skill's scripts/ folder, never from a harness's copy, since the skill's copies are the
source. It replaces each copy that differs apart from line endings, removes a copy it
recorded earlier and no longer ships, and prints one line per file it created, replaced,
or removed, plus a line naming any Rules version change.

It records the SHA-256 of every file it copies in scripts/framework/framework.sha256, in
the format `shasum -a 256 -c` reads, and validate.py checks the harness's rules.md against
that record. It copies nothing and exits 1 when the harness's rules.md is on a newer Rules
version than this skill's, or when any copy differs from its recorded hash, which means it
was edited; each edit is printed as a diff. --restore replaces the edited copies once the
user has agreed. Exits 0 when the copies are current, 1 for those two cases, and 2 when it
cannot run.
"""

import argparse
import datetime
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SOURCE_RULES = SCRIPTS_DIR.parent / "references" / "rules.md"
# The skills a clone of the app's repo holds beside its harness, and what their copies leave out.
COMMITTED_SKILLS = ["vf", "vf-verify", "vf-explain"]
LEFT_OUT_OF_SKILL_COPIES = {"scripts", "__pycache__"}
INSTALL_COMMAND = "npx skills add kennymatsudo/verification-framework"
FRAMEWORK_SCRIPTS = ["validate.py", "code_state.py", "break_session.py", "launch.py", "replay.py", "clip.py",
                     "locate.py", "break_checks.py", "smells.py", "weakened.py", "trust_facts.py", "vf.py"]
SCRIPT_COMMANDS = {
    "validate": ("validate.py", "check the harness's rules copy, settings, feature map, and Verified results"),
    "code-state": ("code_state.py", "print every repo's Git state for an evidence file's code field"),
    "break": ("break_session.py", "run a planned break in a scratch copy of the code under test"),
    "start": ("launch.py", "start the app from the project root and record its process and the code on disk"),
    "stop": ("launch.py", "stop what vf.py start started and remove its launch record"),
    "doctor": ("launch.py", "is the instance vf.py start started running the code on disk, and ready?"),
    "replay": ("replay.py", "build a run's replay page, or recordings.html with --recordings"),
    "clip": ("clip.py", "cut a clip or stills from a recorded run, or --check what this machine can make"),
}
# vf.py run hands a check these two variables: the file it appends events to, and its run folder.
REPORT_VAR = "VERIFY_REPORT"
RUN_DIR_VAR = "VERIFY_RUN_DIR"
EVENTS = ("check", "step", "mark", "recording", "created", "stopped")
CHECK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# A run's folder lives here until its check event names the check.
PENDING = ".pending"
RULES_VERSION_LINE = re.compile(r"^Rules version: (\S+)$", re.MULTILINE)
DOCTOR_TIMEOUT = 120
START_TIMEOUT = 180


class Stopped(Exception):
    """A command cannot run; the message says why."""


def checkout_env(harness, validate, code_state, only=None, missing="error"):
    """The environment a doctor or check runs in: this process's, plus VERIFY_CHECKOUT_<REPO> for each repo the run
    records (the `only` ones, else every repo); with missing="skip", a repo with no checkout here is left out."""
    try:
        checkouts = code_state.recorded_checkouts(harness, {}, only, missing)
    except code_state.StateError as error:
        raise Stopped(str(error)) from error
    return {**os.environ, **code_state.checkout_env(checkouts)}


def needed_repos(harness, validate, command):
    """The repos the behaviors this exact command proves run, from their proof lines' Repos clauses, or None when
    the map does not prove any behavior with this command (every repo is recorded then) or a proof line names none."""
    try:
        _, proofs, _ = feature_map(harness, validate)
    except Stopped:
        return None
    ids = mapped_to_command(harness, validate, command)
    if not ids:
        return None
    repos = settings_repos(harness, validate)
    needed = []
    for sub_id in ids:
        if validate.proof_repos(proofs.get(sub_id)) is None:
            return None
        needed += [name for name in validate.behavior_repos(proofs[sub_id], repos) if name not in needed]
    return needed


def uncovered_repo_problems(harness, validate, record):
    """A problem for each repo a claimed behavior's proof line names that the record did not record."""
    try:
        _, proofs, _ = feature_map(harness, validate)
    except Stopped:
        return []
    repos = settings_repos(harness, validate)
    code = record.get("code") if isinstance(record.get("code"), dict) else {}
    problems = []
    for sub_id in record.get("sub_features") or []:
        proof = proofs.get(sub_id)
        if proof is None or validate.proof_kind(proof) != "command":
            continue
        for name in validate.behavior_repos(proof, repos):
            if name not in code:
                problems.append(f"records no code version for {name}, which {sub_id} runs")
    return problems


def run_doctor(harness, validate, env):
    """The doctor's verdict on the running instance, as the evidence records it: {"exit_code", "output"}.
    Raises Stopped when settings name no doctor."""
    command = validate.setting(harness, "Commands", "Doctor")
    if not command:
        raise Stopped("settings.md has no Doctor line under Commands; vf.py run checks the app is ready before every check")
    try:
        result = subprocess.run(command, shell=True, cwd=validate.project_root(harness), stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=DOCTOR_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "output": f"`{command}` took over {DOCTOR_TIMEOUT}s"}
    output = (result.stdout + result.stderr).strip().splitlines()
    return {"exit_code": result.returncode, "output": "\n".join(output[-40:])}


def ready(doctor):
    """Whether the doctor's verdict lets a check run."""
    return doctor.get("exit_code") == 0


def not_ready_message(doctor):
    """Why no check ran, from a doctor verdict that was not ready, with the doctor's output."""
    exit_code = doctor.get("exit_code")
    head = "the doctor could not tell whether the app is ready" if exit_code == 2 else "the app is not ready"
    detail = doctor.get("output") or ""
    return f"{head} (doctor exited {exit_code if exit_code is not None else 'on a timeout'}); no check ran" + (f":\n{detail}" if detail else "")


def sibling(name):
    """A framework script beside this one, loaded by path so this runs under `python3 -I`."""
    spec = importlib.util.spec_from_file_location(f"harness_{name}", SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now():
    """The current UTC time to the second, the precision evidence timestamps carry."""
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def parse_planned_break(planned, repo):
    """VERIFY_PLANNED_BREAK as the evidence records it, with the repo the break edited, or None when it is not set."""
    if not planned:
        return None
    ids, _, what = planned.partition(": ")
    return {"what": what.strip(), "sub_features": [item.strip() for item in ids.split(",") if item.strip()], "repo": repo}


def report_events(report):
    """The events a check appended to its report file, with a problem for each line that is not one."""
    events, problems = [], []
    for number, line in enumerate(report.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"report line {number} is not JSON: {line[:80]}")
            continue
        if not isinstance(event, dict) or event.get("event") not in EVENTS:
            problems.append(f"report line {number} names no event among {', '.join(EVENTS)}: {line[:80]}")
            continue
        events.append(event)
    return events, problems


def kept_file(value, label, run_dir, problems):
    """A file the check reports by name in its run folder, which must exist there; None when it doesn't."""
    if not isinstance(value, str) or not value or "/" in value or value in (".", ".."):
        problems.append(f"names {label} {value!r}, which is not a file name in the run folder")
        return None
    if not (run_dir / value).is_file():
        problems.append(f"names {label} {value}, which is not in the run folder")
        return None
    return value


def assemble(events, exit_code, run_dir, problems):
    """Build the evidence record from a check's events and exit code, adding format problems."""
    record = {"check": None, "sub_features": None, "passed": {0: True, 1: False}.get(exit_code), "reads": None,
              "steps": [], "marks": [], "created": {}, "stopped": None}
    kept = {"recording": None, "snapshots": []}
    if not any(event["event"] == "check" for event in events):
        problems.append("reported no check event; one line of the report names the check and what it reads")
    for event in events:
        kind = event.pop("event")
        if kind == "check":
            if record["check"] is not None:
                problems.append("reported a second check event")
            record["check"], record["sub_features"], record["reads"] = event.get("name"), event.get("sub_features"), event.get("reads")
            if not isinstance(record["check"], str) or not CHECK_NAME.fullmatch(record["check"]):
                problems.append(f"names check {record['check']!r}; a check name is letters, digits, dots, dashes, and underscores")
        elif kind == "step":
            step = dict(event)
            snapshot = step.get("snapshot")
            if snapshot is not None:
                if not isinstance(snapshot, dict):
                    problems.append(f"has step {step.get('name')!r} with a snapshot that is not an object")
                else:
                    for key, value in snapshot.items():
                        if kept_file(value, f"snapshot {key}", run_dir, problems):
                            kept["snapshots"].append((snapshot, key))
            record["steps"].append(step)
        elif kind == "mark":
            if event.get("kind") not in ("step", "action") or not isinstance(event.get("label"), str) or not event["label"]:
                problems.append(f"has a mark that is not a step or action mark with a label: {json.dumps(event)}")
            elif not isinstance(event.get("at"), (int, float)) or isinstance(event.get("at"), bool) or event["at"] < 0:
                problems.append(f"has mark {event['label']!r} with no 'at' time")
            record["marks"].append(event)
        elif kind == "recording":
            if "recording" in record:
                problems.append("reported a second recording")
            record["recording"] = dict(event)
            if kept_file(event.get("video"), "recording", run_dir, problems):
                kept["recording"] = record["recording"]
        elif kind == "created":
            for key, values in event.items():
                if not isinstance(values, list):
                    problems.append(f"has a created entry for {key} that is not a list")
                    continue
                record["created"].setdefault(key, []).extend(values)
        elif kind == "stopped":
            record["stopped"] = event.get("reason") if isinstance(event.get("reason"), str) and event["reason"] else "the check reported it stopped"
    failed = [step.get("name") for step in record["steps"] if isinstance(step, dict) and step.get("passed") is False]
    if exit_code == 0 and record["stopped"]:
        problems.append("reported it stopped but exited 0")
    if exit_code == 0 and failed:
        problems.append(f"exited 0 but step {failed[0]!r} failed")
    if exit_code == 1 and not failed:
        problems.append("exited 1 but no step failed")
    if exit_code not in (0, 1) and record["stopped"] is None:
        record["stopped"] = f"the check exited {exit_code}"
    if not record["marks"]:
        del record["marks"]
    if not record["created"]:
        del record["created"]
    return record, kept


def judged_by_steps(steps):
    """The sub-features a run's steps name, in the order they first appear."""
    judged = []
    for step in steps:
        named = step.get("sub_features") if isinstance(step, dict) else None
        for sub_id in named if isinstance(named, list) else []:
            if isinstance(sub_id, str) and sub_id not in judged:
                judged.append(sub_id)
    return judged


def mapped_to_command(harness, validate, command):
    """The sub-features whose proof line in the feature map is this exact command, in map order.

    A check that stops, or judges nothing, still covers what the map says its command proves,
    so the stop is recorded against them instead of refused."""
    try:
        _, proofs, _ = feature_map(harness, validate)
    except Stopped:
        return []
    mapped = []
    for sub_id, proof in validate.command_proofs(proofs).items():
        try:
            if shlex.split(validate.BACKTICK.search(proof).group(1)) == list(command):
                mapped.append(sub_id)
        except ValueError:
            continue
    return mapped


def unique_stamp(evidence, stamp):
    """The run's timestamp, suffixed when a run in the same second already left a record, so neither overwrites the other."""
    candidate, attempt = stamp, 1
    while (evidence / PENDING / candidate).exists() or any(evidence.glob(f"*/{candidate}.json")):
        attempt += 1
        candidate = f"{stamp}-{attempt}"
    return candidate


def settle_run_folder(evidence, pending, stamp, name, kept):
    """Move the run's folder out of .pending into its check's folder once the check is named, and point the kept
    recording and snapshots at it. Returns the evidence file's path."""
    folder = evidence / name if name else evidence / PENDING
    folder.mkdir(parents=True, exist_ok=True)
    run_dir = folder / stamp
    run_folder = f"{name}/{stamp}" if name else f"{PENDING}/{stamp}"
    if kept["recording"]:
        kept["recording"]["video"] = f"{run_folder}/{kept['recording']['video']}"
    for snapshot, key in kept["snapshots"]:
        snapshot[key] = f"{run_folder}/{snapshot[key]}"
    if any(pending.iterdir()):
        if run_dir != pending:
            pending.replace(run_dir)
    else:
        pending.rmdir()
    if name and not any((evidence / PENDING).iterdir()):
        (evidence / PENDING).rmdir()
    return folder / f"{stamp}.json"


def build_pages(*arguments):
    """Run replay.py with the arguments; the failure text when it fails, else an empty string."""
    built = subprocess.run([sys.executable, str(SCRIPTS_DIR / "replay.py"), *arguments], capture_output=True, text=True)
    return (built.stderr or built.stdout).strip() if built.returncode != 0 else ""


def run_check(command):
    """Run a check, build its evidence file from the events it reports, and accept or refuse it.

    Returns the lines to print and the exit code.
    """
    harness = harness_of(SCRIPTS_DIR, "vf.py run")
    validate, code_state = sibling("validate"), sibling("code_state")
    planned = os.environ.get("VERIFY_PLANNED_BREAK")
    try:
        broken_repo = code_state.break_session_repo(harness) if planned else None
    except code_state.StateError as error:
        raise Stopped(str(error)) from error
    needed = needed_repos(harness, validate, command)
    env = checkout_env(harness, validate, code_state, needed)
    doctor = run_doctor(harness, validate, env)
    if not ready(doctor):
        raise Stopped(not_ready_message(doctor))
    try:
        code_before = code_state.code_state(harness, {}, needed)
    except code_state.StateError as error:
        raise Stopped(str(error)) from error
    harness_before = validate.harness_code(harness, command)
    evidence = harness / "evidence"
    started = utc_now()
    stamp = unique_stamp(evidence, started.strftime("%Y-%m-%dT%H-%M-%SZ"))
    pending = evidence / PENDING / stamp
    pending.mkdir(parents=True, exist_ok=True)
    report = pending.with_suffix(".jsonl")
    report.write_text("")

    exit_code = subprocess.run(command, cwd=validate.project_root(harness),
                               env={**env, REPORT_VAR: str(report), RUN_DIR_VAR: str(pending)}).returncode

    finished = utc_now()
    events, problems = report_events(report)
    record, kept = assemble(events, exit_code, pending, problems)
    if record["sub_features"] in (None, []):
        judged = judged_by_steps(record["steps"])
        # A run that stopped never reached some of what its command proves, so it counts against those too.
        if record["stopped"] is not None or not judged:
            judged += [sub_id for sub_id in mapped_to_command(harness, validate, command) if sub_id not in judged]
        record["sub_features"] = judged
    record.update(code=code_before, harness_code=harness_before, doctor=doctor, started_at=started.strftime(validate.TIME_FORMAT),
                  finished_at=finished.strftime(validate.TIME_FORMAT), planned_break=parse_planned_break(planned, broken_repo))
    name = record["check"] if isinstance(record["check"], str) and CHECK_NAME.fullmatch(record["check"]) else None
    report.unlink()
    path = settle_run_folder(evidence, pending, stamp, name, kept)
    shown = path.relative_to(harness)
    if name:
        try:
            code_after = code_state.code_state(harness, {}, needed)
        except code_state.StateError as error:
            problems.append(f"could not be matched to the code after the run: {error}")
        else:
            problems += validate.run_problems(record, code_before, code_after, validate.harness_code(harness, command))
            problems += uncovered_repo_problems(harness, validate, record)
    if problems:
        refused = path.with_name(path.name + ".refused")
        refused.write_text(json.dumps(record, indent=2) + "\n")
        lines = [f"REFUSED: {shown} {problem}" for problem in problems]
        lines.append(f"Wrote it to {refused.relative_to(harness)}; this run doesn't count. Fix the check and run it again.")
        if failure := build_pages("--recordings"):
            lines.append(f"recordings.html was not rebuilt: {failure}")
        return lines, 2
    record["accepted_by"] = validate.ACCEPTED_BY
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(path)
    lines = [f"Accepted {shown}"]
    if failure := build_pages(str(path)):
        lines.append(f"replay page not built: {failure}")
    elif kept["recording"]:
        lines.append(f"Recording kept. Watch it at {harness / 'recordings.html'}")
    return lines + refresh_status(harness, validate), exit_code


def feature_map(harness, validate):
    """The feature map's sub-feature IDs, their proof lines, and its errors; raises Stopped when the harness has no map."""
    mapped = validate.read_map(harness, validate.project_root(harness))
    if mapped is None:
        raise Stopped(f"{harness} has no feature index at features/README.md")
    _, seen_ids, proofs, errors = mapped
    validate.check_proof_repos(proofs, settings_repos(harness, validate), errors)
    return seen_ids, proofs, errors


def settings_repos(harness, validate):
    """The repos settings.md lists, or none when the harness has no settings yet."""
    settings = harness / "settings.md"
    return validate.parse_repos(validate.sections(settings.read_text())[1])[0] if settings.is_file() else {}


def mapped_verdicts(harness, validate):
    """The feature map's verdicts, or the map's errors; raises Stopped when the harness has no map."""
    seen_ids, proofs, errors = feature_map(harness, validate)
    if errors:
        return None, errors
    return validate.compute_verdicts(harness, seen_ids, proofs, settings_repos(harness, validate)), []


def evidence_warnings(harness, validate):
    """validate.py's warnings about each behavior's latest pass: no pass, a commit HEAD has moved past or
    no longer contains, or uncommitted code, so a reader of status.md learns the pass is not about this checkout."""
    evidence = harness / "evidence"
    if not evidence.is_dir():
        return []
    _, proofs, _ = feature_map(harness, validate)
    return validate.evidence_warnings(evidence, validate.command_proofs(proofs), validate.project_root(harness),
                                      settings_repos(harness, validate))


def refresh_status(harness, validate):
    """Rewrite status.md's Latest results after a run; return the lines to print about it."""
    try:
        verdicts, errors = mapped_verdicts(harness, validate)
    except Stopped as stopped:
        return [f"status.md not refreshed: {stopped}"]
    if errors:
        return [f"status.md not refreshed: the feature map has {len(errors)} error{'s' if len(errors) != 1 else ''}; run vf.py validate"]
    validate.render_status(harness, verdicts)
    return []


def proof_commands(harness, validate, ids):
    """Each named sub-feature's check command from the feature map, as {command: [ids]}, in map order,
    and the IDs with no command. Raises Stopped for an ID the map lacks or a map with errors."""
    seen_ids, proofs, errors = feature_map(harness, validate)
    if errors:
        raise Stopped(f"the feature map has {len(errors)} error{'s' if len(errors) != 1 else ''}; run vf.py validate")
    missing = [sub_id for sub_id in ids if sub_id not in seen_ids]
    if missing:
        raise Stopped(f"not in the feature map: {', '.join(missing)}")
    commands, uncovered = {}, []
    for sub_id in ids:
        proof = proofs.get(sub_id, "")
        if validate.proof_kind(proof) != "command":
            uncovered.append(sub_id)
            continue
        commands.setdefault(validate.BACKTICK.search(proof).group(1), []).append(sub_id)
    return commands, uncovered


def start_app(harness, validate, code_state, env):
    """Run settings.md's Start command with its checkouts filled in and wait for the doctor to report ready; the lines to print."""
    command = validate.setting(harness, "Commands", "Start")
    if not command:
        raise Stopped("settings.md has no Start line under Commands")
    if command.lower() == validate.START_USER:
        raise Stopped("settings.md says only a person starts the app (Start: user); ask the user to start it")
    if command.lower() == validate.START_NONE:
        raise Stopped("settings.md says there is nothing to start (Start: none), yet the doctor reports not ready")
    try:
        command = validate.fill_checkouts(command, code_state.recorded_checkouts(harness, {}, None, "skip"))
    except (ValueError, code_state.StateError) as error:
        raise Stopped(f"settings.md: {error}") from error
    lines = [f"Starting the app: {command}"]
    started = subprocess.run(command, shell=True, cwd=validate.project_root(harness), stdin=subprocess.DEVNULL, env=env)
    if started.returncode:
        raise Stopped(f"`{command}` exited {started.returncode}")
    deadline = time.monotonic() + START_TIMEOUT
    while True:
        doctor = run_doctor(harness, validate, env)
        if ready(doctor):
            return lines + ["The doctor reports the app ready."]
        if time.monotonic() > deadline:
            raise Stopped(f"the app was started but {not_ready_message(doctor)}")
        time.sleep(3)


def verify(harness, ids, start):
    """Run each named sub-feature's check through vf.py run and report its computed result; the lines and exit code."""
    validate, code_state = sibling("validate"), sibling("code_state")
    commands, uncovered = proof_commands(harness, validate, ids)
    lines = []
    if commands and start:
        env = checkout_env(harness, validate, code_state, None, "skip")
        if not ready(run_doctor(harness, validate, env)):
            lines += start_app(harness, validate, code_state, env)
    for command in commands:
        lines.append(f"Running `{command}` for {', '.join(commands[command])}")
        try:
            run_lines, _ = run_check(shlex.split(command))
        except Stopped as stopped:
            return lines + [f"STOPPED: {stopped}"], 2
        lines += run_lines
    verdicts, errors = mapped_verdicts(harness, validate)
    if errors:
        return lines + [f"ERROR {error}" for error in errors], 2
    results = [validate.render_line(sub_id, verdicts[sub_id]) for sub_id in ids]
    verified = all(verdicts[sub_id]["verdict"] == "Verified" for sub_id in ids)
    return lines + results, 0 if verified else 1


def status(harness):
    """Compute every behavior's verdict and write status.md's Latest results; return the lines to print and the exit code."""
    validate = sibling("validate")
    if not (harness / "status.md").exists():
        # A first status.md, so the feature index's link to it resolves and setup can create it with this command.
        validate.render_status(harness, {})
    verdicts, errors = mapped_verdicts(harness, validate)
    if errors:
        return [f"ERROR {error}" for error in errors] + ["status.md not written: fix the feature map first"], 1
    lines = validate.render_status(harness, verdicts)
    warnings = validate.standing_warnings(verdicts) + evidence_warnings(harness, validate)
    return lines + [f"WARN {warning}" for warning in warnings], 0


def not_verified(harness, sub_id, reason, until_break):
    """Record that a behavior's check could not run, or its pass cannot be trusted, and refresh status.md."""
    validate = sibling("validate")
    verdicts, errors = mapped_verdicts(harness, validate)
    if errors:
        return [f"ERROR {error}" for error in errors] + ["nothing recorded: fix the feature map first"], 1
    if sub_id not in verdicts:
        raise Stopped(f"{sub_id} is not a sub-feature in the feature map")
    if not reason.strip():
        raise Stopped("a Not verified record needs a reason")
    entry = validate.record_not_verified(harness, sub_id, reason, until_break)
    verdicts, _ = mapped_verdicts(harness, validate)
    lines = validate.render_status(harness, verdicts)
    recorded = f"Recorded {sub_id}: Not verified. {entry['reason']}"
    warnings = validate.standing_warnings(verdicts)
    return [recorded] + [line for line in lines if line.startswith(f"- {sub_id}: ")] + [f"WARN {w}" for w in warnings], 0


def harness_of(scripts_dir, command="this command"):
    """The harness this copy of vf.py sits in, at scripts/framework/; raises Stopped elsewhere, naming the command."""
    harness = scripts_dir.parent.parent
    if not (harness / "settings.md").is_file():
        raise Stopped(f"{command} works from a harness's scripts/framework/, and {harness} has no settings.md")
    return harness


def normalized(content):
    """Bytes with CRLF line endings turned to LF, so a Git checkout's conversion is not an edit."""
    return content.replace(b"\r\n", b"\n")


def rules_version(content, label):
    """The Rules version a rules file declares, as an integer."""
    match = RULES_VERSION_LINE.search(normalized(content).decode())
    if not match:
        return None
    if not match.group(1).isdigit():
        raise Stopped(f"{label} has Rules version {match.group(1)}, which is not a whole number")
    return int(match.group(1))


def file_hash(content):
    """SHA-256 of a framework file, ignoring line endings."""
    return hashlib.sha256(normalized(content)).hexdigest()


def read_lock(lock):
    """The hashes framework.sha256 records, by harness-relative path, or an empty dict when there is none."""
    if not lock.is_file():
        return {}
    recorded = {}
    for line in lock.read_text().splitlines():
        digest, _, name = line.strip().partition("  ")
        if digest and name:
            recorded[name] = digest
    return recorded


def edit_diff(source, copy, name):
    """A unified diff from the framework's file to the harness's copy."""
    return "\n".join(difflib.unified_diff(
        normalized(source).decode().splitlines(),
        normalized(copy).decode().splitlines(),
        f"vf {name}",
        f"harness {name}",
        lineterm="",
    ))


def newer_harness(harness_rules, source_rules):
    """Why the harness must not be synced from an older framework, or None."""
    harness_version = rules_version(harness_rules, "the harness's rules.md")
    source_version = rules_version(source_rules, "vf's rules.md")
    if harness_version is not None and harness_version > source_version:
        return (
            f"the harness is on Rules version {harness_version}, newer than this skill's {source_version}; "
            "update the installed framework skills instead of downgrading the harness"
        )
    return None


def edited_copies(copies, recorded):
    """The (name, source bytes, copy bytes) of each framework copy edited since sync last recorded it.

    A copy counts as edited when it differs from the hash sync recorded. In a harness synced before
    the record existed, rules.md counts as edited when it differs on the same Rules version, and a
    script is replaced without question.
    """
    edited = []
    for source_path, target, name in copies:
        if not target.is_file():
            continue
        source, copy = source_path.read_bytes(), target.read_bytes()
        if name in recorded:
            is_edit = file_hash(copy) != recorded[name]
        elif name == "rules.md":
            is_edit = (rules_version(copy, "the harness's rules.md") == rules_version(source, "vf's rules.md")
                       and normalized(copy) != normalized(source))
        else:
            is_edit = False
        if is_edit:
            edited.append((name, source, copy))
    return edited


def source_skill_dir(name):
    """The installed folder of a framework skill, beside vf (the plugin and the skills CLI install them side by side,
    possibly through a symlink), or None when it isn't installed."""
    for skills_dir in (SCRIPTS_DIR.parent.parent, SCRIPTS_DIR.parent.resolve().parent):
        if (skills_dir / name / "SKILL.md").is_file():
            return skills_dir / name
    return None


def skill_files(skill_dir):
    """The files of a skill its committed copy carries, relative to the skill: everything but scripts/ and Python caches."""
    return sorted(
        path.relative_to(skill_dir) for path in skill_dir.rglob("*")
        if path.is_file()
        and not LEFT_OUT_OF_SKILL_COPIES & set(path.relative_to(skill_dir).parts)
        and path.suffix not in (".pyc", ".pyo")
    )


def skills_directories(harness_dir):
    """The skills directory holding the harness first, then every other known one at the project root, so each
    agent the team uses finds the committed skills."""
    own = harness_dir.parent
    known = sibling("locate").SKILLS_DIRS
    project_root = own.parent.parent
    if own not in (project_root / d for d in known):
        return [own]
    return [own] + [project_root / d for d in known if project_root / d != own and (project_root / d).is_dir()]


def committed_skill_copies(harness_dir):
    """(source, target, harness-relative name) for every file of every committed skill, in every skills directory."""
    copies = []
    for name in COMMITTED_SKILLS:
        source_dir = source_skill_dir(name)
        if source_dir is None:
            raise Stopped(f"{name} is not installed beside vf, so its copy cannot be committed beside the harness; "
                          f"install it with `{INSTALL_COMMAND}`")
        for skills_dir in skills_directories(harness_dir):
            for rel in skill_files(source_dir):
                target = skills_dir / name / rel
                copies.append((source_dir / rel, target, Path(os.path.relpath(target, harness_dir)).as_posix()))
    return copies


def sync(harness_dir, restore=False):
    """Bring a harness's framework copies up to date; return the lines to print and the exit code."""
    if not SOURCE_RULES.is_file():
        raise Stopped("no references/rules.md beside this script; run sync from the installed vf skill's scripts/vf.py. "
                      f"This is a harness's copy: updating needs the framework installed, with `{INSTALL_COMMAND}` "
                      "or the Claude Code plugin the README names")
    source_rules = SOURCE_RULES.read_bytes()
    harness_rules_path = harness_dir / "rules.md"
    harness_rules = harness_rules_path.read_bytes() if harness_rules_path.is_file() else None
    framework_dir = harness_dir / "scripts" / "framework"
    lock = harness_dir / sibling("validate").FRAMEWORK_LOCK
    copies = [(SOURCE_RULES, harness_rules_path, "rules.md")]
    copies += [(SCRIPTS_DIR / name, framework_dir / name, str(Path("scripts") / "framework" / name)) for name in FRAMEWORK_SCRIPTS]
    copies += committed_skill_copies(harness_dir)

    if harness_rules is not None:
        conflict = newer_harness(harness_rules, source_rules)
        if conflict:
            return [f"STOPPED: {conflict}"], 1
    recorded = read_lock(lock)
    edited = edited_copies(copies, recorded)
    if edited and not restore:
        names = ", ".join(name for name, _, _ in edited)
        lines = [f"STOPPED: {names} edited since the last sync; app specifics belong in settings.md. "
                 "Rerun with --restore once the user agrees to replace the edited copies."]
        lines += [edit_diff(source, copy, name) for name, source, copy in edited]
        return lines, 1

    lines = []
    if harness_rules is not None:
        old_version = rules_version(harness_rules, "the harness's rules.md")
        new_version = rules_version(source_rules, "vf's rules.md")
        if old_version != new_version:
            lines.append(f"Rules version {old_version if old_version is not None else 'none'} -> {new_version}")
    framework_dir.mkdir(parents=True, exist_ok=True)
    for source, target, name in copies:
        existed = target.is_file()
        if existed and normalized(target.read_bytes()) == normalized(source.read_bytes()):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
        lines.append(f"{'replaced' if existed else 'created'} {name}")
    shipped = {name for _, _, name in copies}
    for name in recorded:
        stale = harness_dir / name
        if name not in shipped and stale.is_file():
            stale.unlink()
            lines.append(f"removed {name}")
    lock_text = "".join(f"{file_hash(source.read_bytes())}  {name}\n" for source, _, name in copies)
    if not lock.is_file() or lock.read_text() != lock_text:
        lines.append(f"{'replaced' if lock.is_file() else 'created'} {lock.relative_to(harness_dir)}")
        lock.write_text(lock_text)
    return lines or ["framework copies already current"], 0


def main():
    # The script commands and run pass their arguments through untouched, so they are dispatched before argparse sees them.
    if len(sys.argv) > 1 and sys.argv[1] in SCRIPT_COMMANDS:
        script = SCRIPTS_DIR / SCRIPT_COMMANDS[sys.argv[1]][0]
        # launch.py holds several commands, so it is told which one; the other scripts are one command each.
        passed = [sys.argv[1], *sys.argv[2:]] if script.name == "launch.py" else sys.argv[2:]
        return subprocess.run([sys.executable, str(script), *passed]).returncode

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        command = sys.argv[3:] if sys.argv[2:3] == ["--"] else sys.argv[2:]
        if not command or command[0].startswith("-"):
            print("usage: vf.py run -- CHECK COMMAND...", file=sys.stderr)
            return 2
        try:
            lines, code = run_check(command)
        except Stopped as stopped:
            print(f"STOPPED: {stopped}", file=sys.stderr)
            return 2
        print("\n".join(lines), flush=True)
        return code

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="run a check and accept the evidence it writes only when it is sound", add_help=False)
    for name, (_, summary) in SCRIPT_COMMANDS.items():
        commands.add_parser(name, help=summary, add_help=False)
    verify_parser = commands.add_parser("verify", help="run the named sub-features' checks through vf.py run and report their results")
    verify_parser.add_argument("sub_features", nargs="+", metavar="ID", help="sub-feature IDs from the feature map")
    verify_parser.add_argument("--start", action="store_true", help="run the Start command when the doctor says the app is not ready")
    commands.add_parser("status", help="compute every behavior's verdict from the evidence and write status.md's Latest results")
    not_verified_parser = commands.add_parser("not-verified", help="record that a behavior's check could not run, and refresh status.md")
    not_verified_parser.add_argument("sub_feature", help="the sub-feature ID")
    not_verified_parser.add_argument("reason", help="why it is Not verified, in a sentence")
    not_verified_parser.add_argument("--until-break", action="store_true", help="stands until a later planned break aimed at it, not just a later run")
    sync_parser = commands.add_parser("sync", help="create or update a harness's rules.md, scripts/framework/, and the skill copies beside it")
    sync_parser.add_argument("harness_dir", type=Path)
    sync_parser.add_argument("--restore", action="store_true", help="replace framework copies that were edited")
    args = parser.parse_args()

    try:
        if args.command == "verify":
            lines, code = verify(harness_of(SCRIPTS_DIR), list(dict.fromkeys(args.sub_features)), args.start)
        elif args.command == "status":
            lines, code = status(harness_of(SCRIPTS_DIR))
        elif args.command == "not-verified":
            lines, code = not_verified(harness_of(SCRIPTS_DIR), args.sub_feature, args.reason, args.until_break)
        else:
            lines, code = sync(args.harness_dir.resolve(), args.restore)
    except Stopped as stopped:
        print(f"STOPPED: {stopped}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
