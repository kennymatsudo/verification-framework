#!/usr/bin/env python3
"""Validate a verification harness's settings, feature map, and Verified results against their format, the repo, and the evidence.

Usage: validate.py [HARNESS_DIR] [--require-evidence] [--run-help]

HARNESS_DIR defaults to the harness this script sits in, at scripts/framework/. The harness's
rules.md must be the copy this script ships with, by Rules version and hash. Exits 0 when the map is
valid, 1 when it has errors, 2 when it cannot run. Evidence age is reported as
warnings only; evidence retention and Git tracking belong to the team.
Every current Verified line in status.md's Latest results must agree with the evidence
file it cites and with a break-tested proof in the map whose cited break was aimed at that
sub-feature and failed a step judging it, and whose steps that caught it are still in the
Verified run, judging the same sub-feature. A cited file that is
absent is a warning, since a fresh checkout may not carry evidence; pass
--require-evidence right after recording results to make it an error.
Cited evidence sits at evidence/<check>/<run>.json. Each step in it records its 'at' time,
and a recording it names must sit inside evidence/.
An incomplete setup exits 2 with its recorded blocker and resume action.
The harness keeps features/, status.md, tools.md, and evidence/ inside its directory.
Each tools.md entry needs every field the tool guide template names, a Run from folder that
exists, and a Help command whose script exists; --run-help also runs each Help command, which
must exit 0 within 10 seconds. A token, cookie, password, or key written into tools.md or a
harness script is an error: tools read credentials from the project's connection settings.
"""

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

RULES_VERSION = "1"
RULES_SHA256 = "dd37895360a04f28d8c2a333704f181a7b7deebc71f87bf503f5b05aed14ce6a"
RULES_VERSION_LINE = re.compile(r"^Rules version: (\S+)$", re.MULTILINE)
SUB_FEATURE = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): \S")
PROOF = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (.+)$")
INDEX_LINK = re.compile(r"\]\(([^)#]+\.md)\)")
BACKTICK = re.compile(r"`([^`]+)`")
REQUIRED = ["Sub-features", "How a user reaches it", "How to prove it"]
OPTIONAL = ["Request flow", "Verification plan", "Gotchas"]
REQUIREMENTS = "requirements.md"
CLAUSE = re.compile(r"^- (.+?) \| (.+?) \| (.+)$")
OUTCOME = re.compile(r"^(ids: .+|No check yet|not in source|blocked on decision: .+|out of scope: .+)$")
SETTING = re.compile(r"^- ([A-Z][A-Za-z ]*): (.*)$")
SETTINGS = {
    "Workflow": ["Requirements source"],
    "Commands": ["Start", "Stop", "Doctor", "Ready line", "Probe", "Invariants module", "Settle signal", "Run scratch code", "After an edit"],
}
SETUP_LABELS = ["Target", "Findings", "Looked in", "Blocker", "Next action", "Doctor proof"]
RESULT = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (Verified|Failed|Not verified)\b")
EVIDENCE_CITE = re.compile(r"Evidence: `?([^\s`]+\.json)`?")
# One folder per check keeps evidence/ browsable as runs pile up; rules.md fixes the layout.
EVIDENCE_PATH = re.compile(r"evidence/[^/]+/[^/]+\.json")
REPO = re.compile(r"^- ([a-z0-9][a-z0-9_-]*): (\S+)$")
ENV_LOCATOR = re.compile(r"^env:([^:]+):([A-Za-z_][A-Za-z0-9_]*)$")
TOOL_FIELDS = ["Inputs", "Environment", "Permissions", "Result", "Failure", "Limits"]
RUN_FROM = re.compile(r"^Run from (.+?):\s*$")
HELP = re.compile(r"^Help: `(.+?) --help`")
HELP_TIMEOUT = 10
# A credential pasted from a captured request is the risk; values with $, <, or { are lookups or
# template blanks, and the assignment rule needs a digit so env var names don't match.
CREDENTIALS = [
    ("a bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("a cookie value", re.compile(r"(?i)\bcookie['\"]?\s*[:=]\s*['\"][^'\"$<{]{20,}['\"]")),
    ("a secret value", re.compile(r"(?i)(?:api[_-]?key|token|secret|password|passwd)['\"]?\s*[:=]\s*['\"](?=[^'\"]*\d)[A-Za-z0-9/+_.=-]{16,}['\"]")),
    ("an AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def sections(text):
    """Split markdown at its '## ' headings: the headings in order, and the lines under each."""
    found, current = {}, None
    order = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            order.append(current)
            found[current] = []
        elif current:
            found[current].append(line)
    return order, found


def latest_result_lines(text):
    """The last result line for each behavior is its current claim, even without evidence."""
    _, body = sections(text)
    return {match.group(1): line for line in body.get("Latest results", []) if (match := RESULT.match(line))}


def proof_kind(body):
    """What a 'How to prove it' line offers: none, unreachable, command, or bad or bad-unreachable when malformed."""
    if body.startswith("No check yet"):
        return "none"
    if body.startswith("Unreachable:"):
        return "unreachable" if "Tried" in body else "bad-unreachable"
    if body.startswith("`"):
        return "command"
    return "bad"


def is_break_tested(proof):
    """Whether a check's proof line records a planned break, as 'Break-tested <date>: ...'."""
    return "Break-tested " in proof


def command_path_exists(command, project):
    first = command.split()[0]
    if "/" not in first:
        return True
    return (project / first).exists()


def check_feature(path, project, seen_ids, errors):
    """Check one feature file's sections, sub-feature IDs, and proof lines, adding its IDs to seen_ids.

    Returns the proof line of each sub-feature that has a check.
    """
    order, body = sections(path.read_text())
    name = path.name
    headings = [h for h in order if h not in OPTIONAL]
    if headings != REQUIRED:
        errors.append(f"{name}: sections are {order}, expected {REQUIRED} in order")
        return {}

    ids = []
    for line in body["Sub-features"]:
        if line.startswith("- "):
            match = SUB_FEATURE.match(line)
            if not match:
                errors.append(f"{name}: sub-feature line is not '- <id>: <behavior>': {line}")
                continue
            sub_id = match.group(1)
            if sub_id in seen_ids:
                errors.append(f"{name}: {sub_id} is also defined in {seen_ids[sub_id]}")
            seen_ids[sub_id] = name
            ids.append(sub_id)

    proofs = {}
    for line in body["How to prove it"]:
        if not line.startswith("- "):
            continue
        match = PROOF.match(line)
        if not match:
            errors.append(f"{name}: proof line is not '- <id>: <proof>': {line}")
            continue
        sub_id, proof = match.groups()
        if sub_id in proofs:
            errors.append(f"{name}: {sub_id} has more than one proof line")
        proofs[sub_id] = proof

    check_proofs = {}
    for sub_id in ids:
        if sub_id not in proofs:
            errors.append(f"{name}: {sub_id} has no line under 'How to prove it'")
            continue
        proof = proofs[sub_id]
        kind = proof_kind(proof)
        if kind == "bad":
            errors.append(f"{name}: {sub_id} proof must be a `command`, 'No check yet.', or 'Unreachable: ... Tried ...'")
        elif kind == "bad-unreachable":
            errors.append(f"{name}: {sub_id} is Unreachable but does not say what was tried")
        elif kind == "command":
            if not is_break_tested(proof) and "Not break-tested" not in proof:
                errors.append(f"{name}: {sub_id} check does not say 'Break-tested <date>: ...' or 'Not break-tested: ...'")
            # The cited break evidence is a path from the harness, checked with the result it backs.
            for command in BACKTICK.findall(EVIDENCE_CITE.sub("", proof)):
                if not command_path_exists(command, project):
                    errors.append(f"{name}: {sub_id} names `{command}`, but {command.split()[0]} does not exist")
            check_proofs[sub_id] = proof
    for sub_id in proofs:
        if sub_id not in ids:
            errors.append(f"{name}: proof line for {sub_id}, which is not a sub-feature here")
    return check_proofs


def check_requirements(path, seen_ids, errors):
    order, body = sections(path.read_text())
    if "Clauses" not in body:
        errors.append(f"{REQUIREMENTS}: no '## Clauses' section")
        return
    for line in body["Clauses"]:
        if not line.startswith("- "):
            continue
        match = CLAUSE.match(line)
        if not match:
            errors.append(f"{REQUIREMENTS}: clause line is not '- <clause> | <source> | <outcome>': {line}")
            continue
        outcome = match.group(3).strip()
        if not OUTCOME.match(outcome):
            errors.append(f"{REQUIREMENTS}: unknown outcome '{outcome}' for: {match.group(1)}")
            continue
        if outcome.startswith("ids: "):
            for sub_id in (part.strip() for part in outcome[5:].split(",")):
                if sub_id not in seen_ids:
                    errors.append(f"{REQUIREMENTS}: {sub_id} is not a sub-feature in the map")


def parse_repos(body):
    """The repos under settings.md's '## Repos', by name, and an error for each line that is not a valid repo."""
    repos, errors = {}, []
    for line in body.get("Repos", []):
        if not line.startswith("- "):
            continue
        match = REPO.match(line)
        if not match:
            errors.append(f"settings.md: invalid repo line: {line}")
            continue
        name, locator = match.groups()
        if name in repos:
            errors.append(f"settings.md: duplicate repo {name}")
        if locator.startswith("env:") and not ENV_LOCATOR.match(locator):
            errors.append(f"settings.md: invalid locator for {name}")
        elif re.search(r"<[a-z]", locator):
            errors.append(f"settings.md: {name} has an unfilled repo locator")
        repos[name] = locator
    return repos, errors


def check_settings(path, errors):
    """Check settings.md's required labels and repo list, and that status.md and tools.md exist. Returns the repos by name."""
    _, body = sections(path.read_text())
    for section, labels in SETTINGS.items():
        values = {}
        for line in body.get(section, []):
            match = SETTING.match(line)
            if match:
                values[match.group(1)] = match.group(2).strip()
        for label in labels:
            value = values.get(label)
            if not value:
                errors.append(f"settings.md: no '- {label}: <value>' line under '## {section}'")
            elif re.search(r"<[a-z]", value):
                errors.append(f"settings.md: {label} still has an unfilled slot: {value}")

    repos, repo_errors = parse_repos(body)
    errors.extend(repo_errors)
    if "Repos" not in body:
        errors.append("settings.md: no '## Repos' section")
    elif not repos:
        errors.append("settings.md: no repos listed under '## Repos'")
    for filename in ("README.md", "status.md", "tools.md"):
        if not (path.parent / filename).is_file():
            errors.append(f"{filename} is missing from the harness")
    for name, locator in repos.items():
        if Path(locator).is_absolute() or locator.startswith("~"):
            errors.append(f"settings.md: {name} locator must be portable")
    return repos


def check_tools(harness_dir, project, run_help, errors):
    """Check each tools.md entry's fields and Help command, running it when run_help is set."""
    order, body = sections((harness_dir / "tools.md").read_text())
    for entry in order:
        lines = [line.strip() for line in body[entry]]
        label = f"tools.md '{entry}'"
        if not any(line.startswith("Use when:") for line in lines):
            errors.append(f"{label}: no 'Use when:' line")
        for field in TOOL_FIELDS:
            if not any(line.startswith(f"- {field}:") for line in lines):
                errors.append(f"{label}: no '- {field}:' line")
        run_from = next((match.group(1).strip("` ") for line in lines if (match := RUN_FROM.match(line))), None)
        if run_from is None:
            errors.append(f"{label}: no 'Run from <folder>:' line")
            continue
        folder = project if run_from in (".", "the project root") else project / run_from
        if not folder.is_dir():
            errors.append(f"{label}: runs from {run_from}, which is not a folder under the project root")
            continue
        command = next((match.group(1) for line in lines if (match := HELP.match(line))), None)
        if command is None:
            errors.append(f"{label}: no 'Help: `<command> --help`' line")
            continue
        script = next((word for word in command.split() if "/" in word and not word.startswith("-")), None)
        if script and not (folder / script).exists():
            errors.append(f"{label}: {script} does not exist in {run_from}")
            continue
        if run_help:
            try:
                ran = subprocess.run(
                    f"{command} --help", shell=True, cwd=folder, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=HELP_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                errors.append(f"{label}: '{command} --help' took over {HELP_TIMEOUT}s; help must not connect to anything")
                continue
            if ran.returncode != 0:
                errors.append(f"{label}: '{command} --help' exited {ran.returncode}")


def credential_errors(harness_dir):
    """Report each line in tools.md or a harness script that holds what looks like a credential, without echoing it."""
    scripts = harness_dir / "scripts"
    files = [harness_dir / "tools.md"]
    if scripts.is_dir():
        files += sorted(
            path for path in scripts.rglob("*")
            if path.is_file() and path.relative_to(scripts).parts[0] != "framework" and "__pycache__" not in path.parts
        )
    errors = []
    for path in files:
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in CREDENTIALS:
                if pattern.search(line):
                    where = path.relative_to(harness_dir)
                    errors.append(f"{where}:{number} holds what looks like {kind}; read it from the project's connection settings")
                    break
    return errors


def rules_sha256(data):
    """SHA-256 of a rules file's bytes."""
    return hashlib.sha256(data).hexdigest()


def check_rules(harness_dir, errors):
    """Check that the harness's rules.md is the copy this script ships with."""
    rules = harness_dir / "rules.md"
    if not rules.is_file():
        errors.append("rules.md is missing; copy it unchanged from setup-verification")
        return
    # Normalize line endings so a Git checkout's conversion is not an edit.
    data = rules.read_bytes().replace(b"\r\n", b"\n")
    match = RULES_VERSION_LINE.search(data.decode())
    version = match.group(1) if match else "none"
    if version != RULES_VERSION:
        errors.append(
            f"rules.md is Rules version {version} but scripts/framework/ is version {RULES_VERSION}; "
            "copy both unchanged from the same framework version"
        )
    elif rules_sha256(data) != RULES_SHA256:
        errors.append("rules.md was edited; restore it unchanged from setup-verification and put app specifics in settings.md")


def check_setup(harness_dir, errors):
    """Check the Setup status in settings.md against the Setup record in status.md.

    Returns the record when setup is incomplete, so the run can stop with its blocker, and None otherwise.
    """
    settings_path = harness_dir / "settings.md"
    if not settings_path.is_file():
        errors.append("settings.md is missing; the harness's settings belong there")
        return None
    _, body = sections(settings_path.read_text())
    status = dict(
        match.groups() for line in body.get("Setup", []) if (match := SETTING.match(line))
    ).get("Status")
    if status not in ("incomplete", "ready"):
        errors.append("settings.md: Setup Status must be incomplete or ready")
        return None
    results = "status.md"
    results_path = harness_dir / results
    try:
        results_text = results_path.read_text()
    except OSError:
        errors.append(f"setup results cannot be read at {results_path}")
        return None
    _, results_body = sections(results_text)
    heading = f"Setup: {harness_dir.name}"
    if results_text.splitlines().count(f"## {heading}") != 1:
        errors.append(f"{results}: expected one '{heading}' section for this harness")
        return None
    record = dict(
        match.groups() for line in results_body[heading] if (match := SETTING.match(line))
    )
    for label in SETUP_LABELS:
        value = record.get(label, "").strip()
        if not value or re.search(r"<[a-z]", value):
            errors.append(f"{results}: Setup needs a filled {label} line")
    if status == "incomplete":
        for label in ("Blocker", "Next action"):
            if record.get(label, "").strip().lower() == "none":
                errors.append(f"{results}: incomplete setup needs a {label}")
        return record
    proof = record.get("Doctor proof", "").strip().lower()
    if proof == "none" or proof.startswith("not run"):
        errors.append(f"{results}: ready setup needs doctor proof")
    for label in ("Blocker", "Next action"):
        if record.get(label, "").strip().lower() != "none":
            errors.append(f"{results}: ready setup still has a {label}")
    return None


def git(directory, *args):
    """Git's trimmed output in directory, or None when the command fails."""
    result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def project_root(harness_dir):
    """The folder holding the skills directory the harness sits in: `app/` for `app/.agents/skills/verify-app/`.

    Recipe commands run from it, and settings.md's repo locators and env: files resolve from it.
    In a single-repo app it is the Git top level; in a monorepo it is the app's own folder.
    """
    return Path(harness_dir).resolve().parents[2]


def resolve_repo(locator, project):
    """The checkout a Repos locator points at, reading env: locators from their file, or None when there is none.

    A locator may name a folder inside a Git checkout, such as the project's own folder in a monorepo;
    code state then covers only that folder.
    """
    match = ENV_LOCATOR.match(locator)
    if match:
        env_path = project / match.group(1)
        try:
            lines = env_path.read_text().splitlines()
        except OSError:
            return None
        key = match.group(2)
        values = [line.partition("=")[2].strip().strip('"\'') for line in lines if line.startswith(key + "=")]
        if not values or not values[-1]:
            return None
        locator = values[-1]
    path = Path(os.path.expandvars(os.path.expanduser(locator)))
    if not path.is_absolute():
        path = project / path
    return path if git(path, "rev-parse", "--show-toplevel") else None


def read_record(path):
    """The JSON object in an evidence file, or None when it cannot be read or holds something else."""
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def report_absent(message, require_evidence, errors, warnings):
    """A cited file that is absent is a warning, since a fresh checkout may not carry evidence,
    and an error with --require-evidence."""
    (errors if require_evidence else warnings).append(message)


def cited_record(harness_dir, cite, subject, label, require_evidence, errors, warnings):
    """The evidence record a result cites, or None once the reason it cannot be used is reported."""
    if not EVIDENCE_PATH.fullmatch(cite):
        errors.append(f"{label}, but {subject} is not at evidence/<check>/<run>.json")
        return None
    path = harness_dir / cite
    if not path.is_file():
        report_absent(f"{label}, but {subject} is not here", require_evidence, errors, warnings)
        return None
    record = read_record(path)
    if record is None:
        errors.append(f"{label}, but {subject} is not a readable JSON object")
    return record


def evidence_warnings(evidence_dir, check_proofs, project, repos):
    """Warnings about each checked sub-feature's latest passing evidence, and about checkouts with uncommitted code now."""
    latest = {}
    for path in sorted(evidence_dir.glob("*/*.json")):
        record = read_record(path)
        if (record is None or record.get("passed") is not True or not isinstance(record.get("sub_features"), list)
                or record.get("planned_break") is not None):
            continue
        for sub_id in record.get("sub_features", []):
            if not isinstance(sub_id, str):
                continue
            if sub_id not in latest or record.get("finished_at", "") > latest[sub_id].get("finished_at", ""):
                latest[sub_id] = record

    # Group by message so a stale repo prints once with every sub-feature it affects.
    subs_by_message = {}
    checkouts = {}
    for sub_id in sorted(check_proofs):
        record = latest.get(sub_id)
        if not record:
            subs_by_message.setdefault("no passing evidence", []).append(sub_id)
            continue
        code = record.get("code") if isinstance(record.get("code"), dict) else {}
        for name, locator in repos.items():
            source = code.get(name) if isinstance(code.get(name), dict) else {}
            commit = source.get("commit") if isinstance(source.get("commit"), str) else None
            if name not in checkouts:
                checkouts[name] = resolve_repo(locator, project)
            checkout = checkouts[name]
            if not checkout:
                subs_by_message.setdefault(f"{name} checkout cannot be found from settings.md", []).append(sub_id)
                continue
            head = git(checkout, "rev-parse", "HEAD")
            tested = git(checkout, "rev-parse", commit) if commit else None
            behind = git(checkout, "rev-list", "--count", f"{commit}..HEAD") if commit else None
            if behind is None or head is None or tested is None:
                message = f"{name} last pass ran on {commit or 'an unknown commit'}, which this checkout cannot find"
            elif tested != head and behind != "0":
                message = f"{name} last pass is {behind} commit{'' if behind == '1' else 's'} behind HEAD"
            elif tested != head:
                message = f"{name} last pass ran on a different commit than HEAD"
            else:
                message = None
            if message:
                subs_by_message.setdefault(message, []).append(sub_id)
            if source.get("dirty"):
                subs_by_message.setdefault(f"{name} last pass used uncommitted code", []).append(sub_id)

    warnings = [f"{message} for {', '.join(subs)}" for message, subs in subs_by_message.items()]
    for name, checkout in checkouts.items():
        changed = uncommitted_files(checkout, evidence_dir.parent) if checkout else None
        if changed:
            more = f" and {len(changed) - 3} more" if len(changed) > 3 else ""
            warnings.append(f"{name} checkout has uncommitted code now: {', '.join(changed[:3])}{more}")
    return warnings


def source_pathspec(checkout, harness_dir):
    """Exclude this harness in its own checkout and in worktrees of the same repo."""
    harness = harness_dir.resolve()
    root = Path(git(harness, "rev-parse", "--show-toplevel") or checkout).resolve()
    if not harness.is_relative_to(root):
        return ["."]
    owner_git = git(root, "rev-parse", "--git-common-dir")
    checkout_git = git(checkout, "rev-parse", "--git-common-dir")
    if owner_git and checkout_git and (root / owner_git).resolve() == (checkout / checkout_git).resolve():
        # top: the path is from the repo's top, whichever folder inside it git runs in.
        return [".", f":(top,exclude){harness.relative_to(root)}"]
    return ["."]


def uncommitted_files(checkout, harness_dir):
    """Dirty as rules.md defines it: modified, staged, or untracked files, not ignored ones,
    outside the harness's own directory. None when git status fails."""
    result = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain", "--", *source_pathspec(checkout, harness_dir)], capture_output=True, text=True
    )
    return [line[3:] for line in result.stdout.splitlines()] if result.returncode == 0 else None


def judged_by(step, record):
    """The sub-features a step judges: its own list, or the run's one sub-feature when it names none.

    A step that names none in a run covering several judges none, so a setup step or a knock-on
    failure can never earn a behavior credit.
    """
    if "sub_features" in step:
        return step["sub_features"]
    ids = record.get("sub_features")
    return ids if isinstance(ids, list) and len(ids) == 1 else []


def steps_judging(record, sub_id):
    """The steps of a run that judge sub_id."""
    return [step for step in record.get("steps") or [] if isinstance(step, dict) and sub_id in judged_by(step, record)]


def check_run_record(record, repos, label, errors):
    """Validate the fields used to connect a result to a completed check and its code."""
    problems = []
    if not isinstance(record.get("check"), str) or not record["check"].strip():
        problems.append("has no check name")
    ids = record.get("sub_features")
    if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids):
        problems.append("has invalid sub_features")
        ids = []
    planned = record.get("planned_break")
    if planned is not None:
        targets = planned.get("sub_features") if isinstance(planned, dict) else None
        if not isinstance(planned, dict) or not isinstance(planned.get("what"), str) or not planned["what"].strip():
            problems.append("has a planned_break that does not say what was broken")
        elif not isinstance(targets, list) or not targets or not all(isinstance(item, str) and item in ids for item in targets):
            problems.append("has a planned_break whose sub_features are not among the run's")
    if record.get("stopped") is not None:
        problems.append("records a stopped run")
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps:
        problems.append("has no check steps")
    else:
        names = set()
        for step in steps:
            if (not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"].strip()
                    or not isinstance(step.get("passed"), bool)):
                problems.append("has an invalid step")
                continue
            if step["name"] in names:
                problems.append(f"has duplicate step '{step['name']}'")
            names.add(step["name"])
            judged = step.get("sub_features", ids)
            if not isinstance(judged, list) or not all(isinstance(item, str) and item in ids for item in judged):
                problems.append(f"has step '{step['name']}' whose sub_features are not among the run's")
        if record.get("passed") is True and any(not isinstance(step, dict) or step.get("passed") is not True for step in steps):
            problems.append("has a step that did not pass")
        untimed = [str(step.get("name", "?")) if isinstance(step, dict) else "?" for step in steps
                   if not isinstance(step, dict) or not is_seconds(step.get("at"))]
        if untimed:
            problems.append(f"has steps with no 'at' time: {', '.join(untimed)}")
    code = record.get("code")
    if not isinstance(code, dict) or not code:
        problems.append("records no code version")
    else:
        for repo in repos:
            if repo not in code:
                problems.append(f"records no code version for {repo}")
        for repo, source in code.items():
            if (not isinstance(source, dict) or not isinstance(source.get("commit"), str)
                    or not re.fullmatch(r"[0-9a-f]{7,40}", source["commit"]) or not isinstance(source.get("dirty"), bool)):
                problems.append(f"has an invalid code version for {repo}")
            elif source["dirty"] and (not isinstance(source.get("dirty_hash"), str)
                                      or not re.fullmatch(r"[0-9a-f]{64}", source["dirty_hash"])):
                problems.append(f"has no valid dirty_hash for {repo}")
            elif not source["dirty"] and source.get("dirty_hash") is not None:
                problems.append(f"has a dirty_hash for clean repo {repo}")
    errors.extend(f"{label}, but {problem}" for problem in problems)
    return not problems


def check_results(harness_dir, check_proofs, repos, require_evidence, errors, warnings):
    """Check each current Verified line against its cited evidence and its check's planned break."""
    status = harness_dir / "status.md"
    if not status.is_file():
        return
    for line in latest_result_lines(status.read_text()).values():
        match = RESULT.match(line)
        if not match or match.group(2) != "Verified":
            continue
        sub_id = match.group(1)
        label = f"status.md: {sub_id} is Verified"
        proof = check_proofs.get(sub_id)
        if proof is None:
            errors.append(f"{label}, but the map has no check for it")
        elif not is_break_tested(proof):
            errors.append(f"{label}, but its check is not break-tested")
        cite = EVIDENCE_CITE.search(line)
        if not cite:
            errors.append(f"{label} without 'Evidence: <file>.json'")
            continue
        record = cited_record(harness_dir, cite.group(1), cite.group(1), label, require_evidence, errors, warnings)
        if record is None:
            continue
        if not check_run_record(record, repos, f"{label}: {cite.group(1)}", errors):
            continue
        if record.get("passed") is not True:
            errors.append(f"{label}, but {cite.group(1)} did not pass")
        if record.get("planned_break") is not None:
            errors.append(f"{label}, but {cite.group(1)} is a planned break run")
        if sub_id not in record.get("sub_features", []):
            errors.append(f"{label}, but {cite.group(1)} does not cover it")
        elif not steps_judging(record, sub_id):
            errors.append(f"{label}, but no step in {cite.group(1)} judges it")
        for repo, source in record["code"].items():
            commit = source["commit"]
            named = re.findall(rf"\b{re.escape(repo)} ([0-9a-f]{{7,40}})\b", line)
            if not any(commit.startswith(n) or n.startswith(commit) for n in named):
                errors.append(f"{label}, but does not name {repo} {commit[:7] or '<unknown>'} from {cite.group(1)}")
        check_recording(record, label, cite.group(1), harness_dir / "evidence", require_evidence, errors, warnings)
        if proof and is_break_tested(proof):
            check_break(harness_dir, sub_id, record, proof, repos, label, require_evidence, errors, warnings)


def check_break(harness_dir, sub_id, record, proof, repos, label, require_evidence, errors, warnings):
    """A planned break proves a sub-feature only when it was aimed at that sub-feature and a step
    judging it failed. Those steps must still be in the Verified run, judging the same sub-feature.
    Steps added since only make the check stricter. A step that failed only because an earlier one
    did, such as a receipt step after a payment break, earns its own sub-feature nothing."""
    cite = EVIDENCE_CITE.search(proof)
    if not cite:
        errors.append(f"{label}, but its break-test cites no evidence")
        return
    subject = f"its planned break {cite.group(1)}"
    broken = cited_record(harness_dir, cite.group(1), subject, label, require_evidence, errors, warnings)
    if broken is None:
        return
    where = f"its planned break in {cite.group(1)}"
    if broken.get("passed") is not False:
        errors.append(f"{label}, but {where} did not fail")
    if not check_run_record(broken, repos, f"{label}: {where}", errors):
        return
    if broken["check"] != record["check"]:
        errors.append(f"{label}, but {where} ran a different check ({broken['check']} versus {record['check']})")
    planned = broken.get("planned_break")
    if planned is None:
        errors.append(f"{label}, but {where} does not record a planned_break")
        return
    if sub_id not in planned["sub_features"]:
        errors.append(f"{label}, but {where} was aimed at {', '.join(planned['sub_features'])}, not this sub-feature")
        return
    caught = [step["name"] for step in steps_judging(broken, sub_id) if step["passed"] is False]
    if not caught:
        errors.append(f"{label}, but no step judging it failed in {where}")
    judging = {step["name"] for step in steps_judging(record, sub_id)}
    for name in caught:
        if name not in judging:
            errors.append(f"{label}, but step '{name}' caught its planned break and does not judge it in this run")


def is_seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def check_recording(record, label, cite, evidence_dir, require_evidence, errors, warnings):
    """Check that a cited run's recording, when it has one, sits inside evidence/ and says when it starts."""
    if "recording" not in record:
        return
    recording = record["recording"]
    video = recording.get("video") if isinstance(recording, dict) else None
    if not isinstance(video, str) or not video or Path(video).is_absolute() or ".." in Path(video).parts:
        errors.append(f"{label}, but {cite} does not name its recording by a path inside evidence/")
    elif not is_seconds(recording.get("starts_at")):
        errors.append(f"{label}, but {cite} does not say when its recording starts")
    elif not (evidence_dir / video).is_file():
        report_absent(f"{label}, but its recording {video} is not here", require_evidence, errors, warnings)


def main():
    """Report harness format errors and evidence warnings, enforcing the setup gate."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("harness_dir", nargs="?", default=Path(__file__).resolve().parents[2], type=Path)
    parser.add_argument("--require-evidence", action="store_true", help="fail when a Verified line cites a missing evidence file")
    parser.add_argument("--run-help", action="store_true", help="run each tools.md Help command, which must exit 0 quickly")
    args = parser.parse_args()

    project = project_root(args.harness_dir)
    errors = []
    check_rules(args.harness_dir.resolve(), errors)
    incomplete_setup = check_setup(args.harness_dir.resolve(), errors)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    if incomplete_setup:
        print(f"STOPPED: setup incomplete for {incomplete_setup['Target']}")
        print(f"Blocker: {incomplete_setup['Blocker']}")
        print(f"Next action: {incomplete_setup['Next action']}")
        return 2
    repos = check_settings(args.harness_dir / "settings.md", errors)
    if (args.harness_dir / "tools.md").is_file():
        check_tools(args.harness_dir, project, args.run_help, errors)
    errors.extend(credential_errors(args.harness_dir))
    features_dir = args.harness_dir / "features"
    index = features_dir / "README.md"
    if not index.is_file():
        print(f"STOPPED: no feature index at {index}", file=sys.stderr)
        return 2
    index_text = index.read_text()
    _, index_sections = sections(index_text)
    linked = {link.lstrip("./") for link in INDEX_LINK.findall("\n".join(index_sections.get("Features", [])))}
    for link in set(INDEX_LINK.findall(index_text)):
        if "://" not in link and not (features_dir / link).is_file():
            errors.append(f"README.md links {link}, which does not exist")
    files = {p.name for p in features_dir.glob("*.md") if p.name not in ("README.md", REQUIREMENTS)}
    for unlisted in sorted(files - linked):
        errors.append(f"{unlisted} is not listed in README.md")

    seen_ids, check_proofs = {}, {}
    for name in sorted(files):
        check_proofs.update(check_feature(features_dir / name, project, seen_ids, errors))
    if (features_dir / REQUIREMENTS).is_file():
        check_requirements(features_dir / REQUIREMENTS, seen_ids, errors)

    result_warnings = []
    check_results(args.harness_dir, check_proofs, repos, args.require_evidence, errors, result_warnings)

    for error in errors:
        print(f"ERROR {error}")
    for warning in result_warnings:
        print(f"WARN {warning}")
    evidence_dir = args.harness_dir / "evidence"
    if evidence_dir.is_dir():
        for warning in evidence_warnings(evidence_dir, check_proofs, project, repos):
            print(f"WARN {warning}")
    else:
        print(f"WARN no evidence directory at {evidence_dir}")

    total = len(seen_ids)
    print(f"{len(files)} features, {total} sub-features, {len(check_proofs)} with checks, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
