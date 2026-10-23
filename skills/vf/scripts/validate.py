#!/usr/bin/env python3
"""Validate a verification harness's settings, feature map, and rendered results against their format, the repo, and the evidence.

Usage: validate.py [HARNESS_DIR] [--require-evidence] [--run-help]

HARNESS_DIR defaults to the harness this script sits in, at scripts/framework/. The harness's
rules.md must match the hash vf.py sync recorded for it in scripts/framework/framework.sha256,
so an edited copy, or one from another framework version, fails before anything else. Exits 0 when the map is
valid, 1 when it has errors, 2 when it cannot run. Evidence age is reported as
warnings only; evidence retention and Git tracking belong to the team.
status.md is written by `vf.py status` from the evidence, never by hand; the hand-written
Setup record and notes live in notes.md. A behavior is Verified only when its latest accepted run passed
against a ready app, an accepted planned break of the same check aimed at that sub-feature failed a step
judging it, every step that caught the break still judges it in the passing run, every harness file the
break ran is unchanged in the pass, and no `vf.py not-verified` record written after that run stands.
Every Verified line in the section must be the one `vf.py status` would write now. A cited file that is absent is a warning, since a fresh checkout may not carry
evidence; pass --require-evidence right after recording results to make it an error.
Cited evidence sits at evidence/<check>/<run>.json. Each step in it records its 'at' time,
and a recording it names must sit inside evidence/.
An incomplete setup exits 2 with its recorded blocker and resume action.
The harness keeps features/, notes.md, status.md, tools.md, and evidence/ inside its directory.
Each tools.md entry needs every field the tool guide template names, a Run from folder that
exists, and a Help command whose script exists; --run-help also runs each Help command, which
must exit 0 within 10 seconds. A token, cookie, password, or key written into tools.md or a
harness script is an error: tools read credentials from the project's connection settings.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

# Written by vf.py sync: the SHA-256 of every framework file it copied, so an edit made since shows.
FRAMEWORK_LOCK = Path("scripts") / "framework" / "framework.sha256"
RULES_VERSION_LINE = re.compile(r"^Rules version: (\S+)$", re.MULTILINE)
ACCEPTED_BY = "vf.py run"
# A check that starts the app itself has no instance for the doctor to inspect before it runs.
PER_CHECK = "per check"
SHA256 = re.compile(r"[0-9a-f]{64}")
SUB_FEATURE = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): \S")
PROOF = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (.+)$")
INDEX_LINK = re.compile(r"\]\(([^)#]+\.md)\)")
BACKTICK = re.compile(r"`([^`]+)`")
REQUIRED = ["Sub-features", "How a user reaches it", "How to prove it"]
OPTIONAL = ["Request flow", "Verification plan", "Gotchas"]
SETTING = re.compile(r"^- ([A-Z][A-Za-z ]*): (.*)$")
SETTINGS = {
    "Workflow": ["Requirements source"],
    "Commands": ["Start", "Stop", "Doctor", "Ready line", "Probe", "Run scratch code", "After an edit"],
}
SETUP_LABELS = ["Target", "Findings", "Looked in", "Blocker", "Next action", "Doctor proof"]
RESULT = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (Verified|Failed|Not verified)\b")
RESULTS_HEADING = "Latest results"
RENDERED_NOTE = ("Written by `vf.py status` from the evidence on this machine; every accepted run refreshes it, "
                 "and `vf.py not-verified` records a check that could not run. Edits here are overwritten; "
                 "notes belong in notes.md.")
# Not verified records agents write with vf.py not-verified, one JSON object per line.
NOT_VERIFIED_LOG = Path("evidence") / "not-verified.jsonl"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
EVIDENCE_CITE = re.compile(r"Evidence: `?([^\s`]+\.json)`?")
# One folder per check keeps evidence/ browsable as runs pile up; rules.md fixes the layout.
EVIDENCE_PATH = re.compile(r"evidence/[^/]+/[^/]+\.json")
REPO = re.compile(r"^- ([a-z0-9][a-z0-9_-]*): (\S+)$")
ENV_LOCATOR = re.compile(r"^env:([^:]+):([A-Za-z_][A-Za-z0-9_]*)$")
TOOL_FIELDS = ["Permissions", "Limits"]
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


def setting(harness_dir, section, label):
    """A labeled value from settings.md, without surrounding backticks, or None when the line is missing or blank."""
    path = harness_dir / "settings.md"
    if not path.is_file():
        return None
    _, body = sections(path.read_text())
    for line in body.get(section, []):
        match = SETTING.match(line)
        if match and match.group(1) == label:
            value = match.group(2).strip()
            value = value[1:-1] if len(value) > 1 and value[0] == value[-1] == "`" else value
            return value or None
    return None


def harness_code(harness_dir, command=()):
    """The harness's own code as {path from the project root: SHA-256}: every file under scripts/ apart from
    the framework copies, plus any file the check command names. A planned break and a later pass must agree on it."""
    project = project_root(harness_dir)
    scripts = harness_dir / "scripts"
    files = []
    if scripts.is_dir():
        files += [path for path in scripts.rglob("*")
                  if path.is_file() and path.relative_to(scripts).parts[0] != "framework" and "__pycache__" not in path.parts]
    for word in command:
        if "/" in word and "\n" not in word and not word.startswith("-") and len(word) < 1024 and (project / word).is_file():
            files.append(project / word)
    manifest = {}
    for path in files:
        try:
            key = path.resolve().relative_to(project.resolve()).as_posix()
        except ValueError:
            continue
        manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(manifest.items()))


def command_path_exists(command, project):
    """Whether a proof command's program exists, when it is named by a path from the project root."""
    first = command.split()[0]
    if "/" not in first:
        return True
    return (project / first).exists()


def check_feature(path, project, seen_ids, errors):
    """Check one feature file's sections, sub-feature IDs, and proof lines, adding its IDs to seen_ids.

    Returns each sub-feature's well-formed proof line, in file order.
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

    well_formed = {}
    for sub_id in ids:
        if sub_id not in proofs:
            errors.append(f"{name}: {sub_id} has no line under 'How to prove it'")
            continue
        proof = proofs[sub_id]
        kind = proof_kind(proof)
        if kind == "bad":
            errors.append(f"{name}: {sub_id} proof must be a `command`, 'No check yet.', or 'Unreachable: ... Tried ...'")
            continue
        if kind == "bad-unreachable":
            errors.append(f"{name}: {sub_id} is Unreachable but does not say what was tried")
            continue
        if kind == "command":
            if "Break-tested" in proof:
                errors.append(f"{name}: {sub_id} says Break-tested, but nobody writes that: vf.py status computes it from the evidence")
            for command in BACKTICK.findall(proof):
                if not command_path_exists(command, project):
                    errors.append(f"{name}: {sub_id} names `{command}`, but {command.split()[0]} does not exist")
        well_formed[sub_id] = proof
    for sub_id in proofs:
        if sub_id not in ids:
            errors.append(f"{name}: proof line for {sub_id}, which is not a sub-feature here")
    return well_formed


def command_proofs(proofs):
    """The proof lines that name a check."""
    return {sub_id: proof for sub_id, proof in proofs.items() if proof_kind(proof) == "command"}


def read_map(harness_dir, project):
    """Read and check the feature map.

    Returns (feature file names, sub-feature IDs in map order with their file, each sub-feature's
    proof line, errors), or None when the harness has no feature index.
    """
    features_dir = harness_dir / "features"
    index = features_dir / "README.md"
    if not index.is_file():
        return None
    errors = []
    index_text = index.read_text()
    _, index_sections = sections(index_text)
    linked = {link.lstrip("./") for link in INDEX_LINK.findall("\n".join(index_sections.get("Features", [])))}
    for link in set(INDEX_LINK.findall(index_text)):
        if "://" not in link and not (features_dir / link).is_file():
            errors.append(f"README.md links {link}, which does not exist")
    files = {p.name for p in features_dir.glob("*.md") if p.name != "README.md"}
    for unlisted in sorted(files - linked):
        errors.append(f"{unlisted} is not listed in README.md")
    seen_ids, proofs = {}, {}
    for name in sorted(files):
        proofs.update(check_feature(features_dir / name, project, seen_ids, errors))
    return files, seen_ids, proofs, errors


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
    """Check settings.md's required lines and repo list, and that the harness's fixed files exist. Returns the repos by name."""
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
    for filename in ("README.md", "notes.md", "status.md", "tools.md"):
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
    """SHA-256 of a rules file's bytes, the form framework.sha256 records."""
    return hashlib.sha256(data).hexdigest()


def recorded_hash(harness_dir, name):
    """The hash framework.sha256 records for a harness-relative path, or None when it records none."""
    lock = harness_dir / FRAMEWORK_LOCK
    if not lock.is_file():
        return None
    for line in lock.read_text().splitlines():
        digest, _, recorded = line.strip().partition("  ")
        if recorded == name:
            return digest
    return None


def committed_skill_folders(harness_dir):
    """The skill folders vf.py sync wrote beside the harness, found from the paths framework.sha256 records outside
    it. They are framework copies, not the app's code, so the dirty state leaves them out like the harness itself."""
    lock = harness_dir / FRAMEWORK_LOCK
    if not lock.is_file():
        return set()
    folders = set()
    for line in lock.read_text().splitlines():
        _, _, name = line.strip().partition("  ")
        if not name.startswith("../"):
            continue
        path = Path(os.path.normpath(harness_dir / name))
        folder = next((parent for parent in path.parents if (parent / "SKILL.md").is_file()), None)
        if folder is not None:
            folders.add(folder.resolve())
    return folders


def check_rules(harness_dir, errors):
    """Check that the harness's rules.md is the copy vf.py sync recorded, so neither an edit nor another version slips through."""
    rules = harness_dir / "rules.md"
    if not rules.is_file():
        errors.append("rules.md is missing; run vf to update the harness")
        return
    # Normalize line endings so a Git checkout's conversion is not an edit.
    data = rules.read_bytes().replace(b"\r\n", b"\n")
    recorded = recorded_hash(harness_dir, "rules.md")
    if recorded is None:
        errors.append(f"{FRAMEWORK_LOCK} has no entry for rules.md; run vf to bring the harness's framework copies up to date")
    elif rules_sha256(data) != recorded:
        errors.append("rules.md differs from the copy vf last synced; run vf to update or restore it, and put app specifics in settings.md")


def check_written_for(harness_dir, written_for, errors):
    """Fail when the skill running this was written for another Rules version than the harness's rules.md, naming
    the side to update. A skill committed beside the harness always matches; a personal install may not."""
    rules = harness_dir / "rules.md"
    if written_for is None or not rules.is_file():
        return
    match = RULES_VERSION_LINE.search(rules.read_text())
    harness_version = match.group(1) if match else None
    if harness_version == written_for:
        return
    harness_is_older = harness_version is None or (
        harness_version.isdigit() and written_for.isdigit() and int(harness_version) < int(written_for))
    fix = ("update the harness: run vf's update mode from an installed framework" if harness_is_older
           else "update the installed framework skills, since the harness's copies are newer")
    errors.append(f"this skill was written for Rules version {written_for} and the harness's rules.md is on "
                  f"{harness_version if harness_version is not None else 'no version'}; {fix}")


def check_setup(harness_dir, errors):
    """Check the Setup status in settings.md against the Setup record in notes.md.

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
    notes = "notes.md"
    notes_path = harness_dir / notes
    try:
        notes_text = notes_path.read_text()
    except OSError:
        errors.append(f"the Setup record cannot be read at {notes_path}")
        return None
    _, notes_body = sections(notes_text)
    heading = f"Setup: {harness_dir.name}"
    if notes_text.splitlines().count(f"## {heading}") != 1:
        errors.append(f"{notes}: expected one '{heading}' section for this harness")
        return None
    record = dict(
        match.groups() for line in notes_body[heading] if (match := SETTING.match(line))
    )
    for label in SETUP_LABELS:
        value = record.get(label, "").strip()
        if not value or re.search(r"<[a-z]", value):
            errors.append(f"{notes}: Setup needs a filled {label} line")
    if status == "incomplete":
        for label in ("Blocker", "Next action"):
            if record.get(label, "").strip().lower() == "none":
                errors.append(f"{notes}: incomplete setup needs a {label}")
        return record
    proof = record.get("Doctor proof", "").strip().lower()
    if proof == "none" or proof.startswith("not run"):
        errors.append(f"{notes}: ready setup needs doctor proof")
    for label in ("Blocker", "Next action"):
        if record.get(label, "").strip().lower() != "none":
            errors.append(f"{notes}: ready setup still has a {label}")
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


def latest_passing_records(evidence_dir):
    """The newest passing, non-break record covering each sub-feature, as {sub_id: record}."""
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
    return latest


def stale_commit_warning(name, checkout, commit):
    """Why a pass on the commit is not a pass on the checkout's HEAD, or None when the commit is HEAD."""
    head = git(checkout, "rev-parse", "HEAD")
    tested = git(checkout, "rev-parse", commit) if commit else None
    behind = git(checkout, "rev-list", "--count", f"{commit}..HEAD") if commit else None
    if behind is None or head is None or tested is None:
        return f"{name} last pass ran on {commit or 'an unknown commit'}, which this checkout cannot find"
    if tested != head and behind != "0":
        return f"{name} last pass is {behind} commit{'' if behind == '1' else 's'} behind HEAD"
    if tested != head:
        return f"{name} last pass ran on a different commit than HEAD"
    return None


def evidence_warnings(evidence_dir, check_proofs, project, repos):
    """Warnings about each checked sub-feature's latest passing evidence, and about checkouts with uncommitted code now."""
    latest = latest_passing_records(evidence_dir)
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
            message = stale_commit_warning(name, checkout, commit)
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
    """The Git pathspec for a checkout's app code: everything, minus the harness's own folder and the framework
    skill copies sync wrote beside it, when the checkout is the harness's repo or a worktree of it."""
    harness = harness_dir.resolve()
    root = Path(git(harness, "rev-parse", "--show-toplevel") or checkout).resolve()
    if not harness.is_relative_to(root):
        return ["."]
    owner_git = git(root, "rev-parse", "--git-common-dir")
    checkout_git = git(checkout, "rev-parse", "--git-common-dir")
    if owner_git and checkout_git and (root / owner_git).resolve() == (checkout / checkout_git).resolve():
        # top: the path is from the repo's top, whichever folder inside it git runs in.
        excluded = [harness] + sorted(folder for folder in committed_skill_folders(harness) if folder.is_relative_to(root))
        return [".", *(f":(top,exclude){folder.relative_to(root)}" for folder in excluded)]
    return ["."]


def uncommitted_files(checkout, harness_dir):
    """Dirty as rules.md defines it: modified, staged, or untracked files, not ignored ones,
    outside the harness's own directory and the framework skill copies beside it. None when git status fails."""
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


def record_problems(record, repos):
    """Format problems in any run's record: the fields that tie it to its check, its steps, and its code."""
    problems = []
    if not isinstance(record.get("check"), str) or not record["check"].strip():
        problems.append("has no check name")
    ids = record.get("sub_features")
    if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids):
        problems.append("has invalid sub_features")
        ids = []
    if record.get("passed") not in (True, False, None):
        problems.append("has a passed value that is not true, false, or null")
    planned = record.get("planned_break")
    if planned is not None:
        targets = planned.get("sub_features") if isinstance(planned, dict) else None
        if not isinstance(planned, dict) or not isinstance(planned.get("what"), str) or not planned["what"].strip():
            problems.append("has a planned_break that does not say what was broken")
        elif not isinstance(targets, list) or not targets or not all(isinstance(item, str) and item in ids for item in targets):
            problems.append("has a planned_break whose sub_features are not among the run's")
    steps = record.get("steps")
    if not isinstance(steps, list) or (not steps and record.get("passed") is True):
        problems.append("has no check steps")
    elif steps:
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
    # The latest run decides a verdict, so every record needs a time that sorts: UTC, to the second.
    for field in ("started_at", "finished_at"):
        if not isinstance(record.get(field), str) or not TIMESTAMP.fullmatch(record[field]):
            problems.append(f"has no {field} in UTC, such as 2026-10-03T14:02:40Z")
    manifest = record.get("harness_code")
    if not isinstance(manifest, dict) or not all(isinstance(k, str) and isinstance(v, str) and SHA256.fullmatch(v) for k, v in manifest.items()):
        problems.append("records no harness_code fingerprint")
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
    return problems


def code_identity(source):
    """The commit and uncommitted-content fingerprint that identify a repo's code."""
    return (source.get("commit"), source.get("dirty_hash")) if isinstance(source, dict) else (None, None)


def run_problems(record, code_before, code_after, harness_after):
    """Why vf.py run refuses a record a check just wrote, judged against the code before and after the run."""
    problems = record_problems(record, list(code_after))
    changed = sorted(repo for repo in code_after if code_identity(code_before.get(repo)) != code_identity(code_after[repo]))
    if changed:
        problems.append(f"ran while the code changed in {', '.join(changed)}")
    if record.get("harness_code") != harness_after:
        problems.append("ran while the harness's own code changed")
    code = record.get("code") if isinstance(record.get("code"), dict) else {}
    for repo, on_disk in code_after.items():
        commit, dirty_hash = code_identity(code.get(repo))
        if not isinstance(commit, str):
            continue
        if not on_disk["commit"].startswith(commit):
            problems.append(f"records {repo} at commit {commit} but {on_disk['commit'][:12]} was checked out")
        elif dirty_hash != on_disk["dirty_hash"]:
            problems.append(f"records different uncommitted code for {repo} than was on disk")
    return problems


def accepted_run_problems(record, repos):
    """Why a record cannot connect a result to a completed check accepted by vf.py run against its code; empty when it can."""
    problems = record_problems(record, repos)
    if record.get("stopped") is not None:
        problems.append("records a stopped run")
    if record.get("steps") == [] and "has no check steps" not in problems:
        problems.append("has no check steps")
    if record.get("accepted_by") != ACCEPTED_BY:
        problems.append("was not accepted by vf.py run; rerun the check through it")
    doctor = record.get("doctor")
    if doctor != PER_CHECK and not (isinstance(doctor, dict) and doctor.get("exit_code") == 0):
        problems.append("ran without the doctor reporting the app ready")
    return problems


def accepted_records(evidence_dir):
    """Every evidence record vf.py run accepted, as (path, record), oldest first by finished_at."""
    records = []
    for path in sorted(evidence_dir.glob("*/*.json")) if evidence_dir.is_dir() else []:
        record = read_record(path)
        if record is not None and record.get("accepted_by") == ACCEPTED_BY and isinstance(record.get("sub_features"), list):
            records.append((path, record))
    records.sort(key=lambda item: str(item[1].get("finished_at") or ""))
    return records


def not_verified_entries(harness_dir):
    """The records vf.py not-verified wrote, in file order, skipping malformed lines."""
    path = harness_dir / NOT_VERIFIED_LOG
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (isinstance(entry, dict) and all(isinstance(entry.get(key), str) and entry[key].strip()
                                            for key in ("sub_feature", "reason", "at"))):
            entries.append(entry)
    return entries


def record_not_verified(harness_dir, sub_id, reason, until_break=False):
    """Append a Not verified record for sub_id and return it. A later accepted run of a check covering
    the sub-feature lifts it; with until_break, only a later planned break aimed at it does."""
    entry = {"sub_feature": sub_id, "reason": reason.strip(), "at": datetime.datetime.now(datetime.timezone.utc).strftime(TIME_FORMAT)}
    if until_break:
        entry["until"] = "break"
    path = harness_dir / NOT_VERIFIED_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as log:
        log.write(json.dumps(entry) + "\n")
    return entry


def code_summary(record):
    """Each repo's commit, with its uncommitted-content fingerprint when dirty, as `app a1b2c3d (uncommitted 9f8e7d6c)`."""
    parts = []
    for repo, source in (record.get("code") or {}).items():
        if not isinstance(source, dict) or not isinstance(source.get("commit"), str):
            continue
        part = f"{repo} {source['commit'][:7]}"
        if source.get("dirty") and isinstance(source.get("dirty_hash"), str):
            part += f" (uncommitted {source['dirty_hash'][:8]})"
        parts.append(part)
    return ", ".join(parts) or "unknown code"


def sentence(text):
    """The text with a full stop at the end, unless it already ends one."""
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def capitalized(text):
    """The text as a sentence that starts with a capital letter."""
    text = sentence(text)
    return text[:1].upper() + text[1:]


def verdict(kind, text, problems, cite=None, absent_video=(), standing=None):
    """One behavior's computed result. problems say, after '<id> is Verified, but', why it is not Verified;
    standing is the Not verified record that decided it."""
    return {"verdict": kind, "text": text, "problems": problems, "cite": cite,
            "absent_video": list(absent_video), "standing": standing}


def compute_verdict(harness_dir, sub_id, proof, records, entries, repos):
    """A behavior's verdict from its proof line, the accepted evidence, and the Not verified records.

    Verified needs the latest accepted run of a check covering the behavior to have passed against a
    ready app, the newest accepted planned break of that check aimed at it to have failed a step judging
    it, those steps to still judge it in the passing run, every harness file the break ran to be unchanged,
    every harness file the passing run ran to be unchanged on disk, and no standing Not verified record
    written after the run. Anything less is Failed, when the latest
    run failed, or Not verified with the reason.
    """
    kind = proof_kind(proof)
    if kind == "none":
        return verdict("Not verified", "No check yet.", ["the map has no check for it"])
    if kind == "unreachable":
        return verdict("Not verified", sentence(proof), ["the map says it is unreachable"])

    runs = [(path, record) for path, record in records if sub_id in record["sub_features"] and record.get("planned_break") is None]
    breaks = aimed_breaks(records, sub_id)
    latest = runs[-1] if runs else None

    standing = standing_not_verified(sub_id, entries, latest, breaks)
    if standing:
        day = standing["at"][:10]
        note = f"Recorded {day}; a new planned break lifts it." if standing.get("until") == "break" else f"Recorded {day}."
        return verdict("Not verified", f"{capitalized(standing['reason'])} {note}",
                       [f"it was recorded Not verified on {day}: {standing['reason']}"], standing=standing)

    if latest is None:
        note = not_break_tested_reason(proof)
        text = "No accepted run on this machine." + (f" {capitalized(note)}" if note else "")
        return verdict("Not verified", text, ["no accepted run covers it"])

    path, record = latest
    cite = path.relative_to(harness_dir).as_posix()
    code = code_summary(record)
    if record.get("passed") is False:
        failed = [step for step in steps_judging(record, sub_id) if step.get("passed") is False]
        failed = failed or [step for step in record.get("steps") or [] if isinstance(step, dict) and step.get("passed") is False]
        where = "A step failed"
        if failed:
            where = f"Step '{failed[0].get('name', '?')}'" + (f": {failed[0]['detail']}" if failed[0].get("detail") else "")
        text = f"{where}. {code}. Evidence: {cite}"
        replay = path.with_suffix("") / "replay.html"
        if replay.is_file():
            text += f". Replay: {replay.relative_to(harness_dir).as_posix()}"
        return verdict("Failed", text, [f"its latest run {cite} did not pass"], cite)
    if record.get("passed") is not True:
        return verdict("Not verified", f"Run stopped: {capitalized(str(record.get('stopped') or 'no verdict'))} {code}. Evidence: {cite}",
                       [f"its latest run {cite} stopped"], cite)
    problems = accepted_run_problems(record, repos) + harness_edited_since_run(harness_dir, record)
    if not steps_judging(record, sub_id):
        problems.append(f"no step in {cite} judges it")
    absent_video = []
    check_recording(record, cite, harness_dir / "evidence", False, problems, absent_video)
    broken = latest_break(breaks, record)
    if not problems and broken is None:
        note = not_break_tested_reason(proof) or "no planned break aimed at it has failed this check"
        return verdict("Not verified", f"Passed but not break-tested: {sentence(note)} {code}. Evidence: {cite}",
                       ["its check is not break-tested"], cite)
    if not problems:
        check_break(harness_dir, sub_id, record, broken, repos, problems)
    if problems:
        return verdict("Not verified", f"Pass not proven: {sentence(problems[0])} {code}. Evidence: {cite}", problems, cite,
                       absent_video=absent_video)
    parts = [str(record["check"])]
    if isinstance(record.get("reads"), str) and record["reads"]:
        parts.append(f"reads {record['reads']}")
    parts.append(code)
    _, broken_record = broken
    tested = f"Break-tested {str(broken_record.get('finished_at', ''))[:10]}: {broken_record['planned_break']['what']}"
    return verdict("Verified", f"{', '.join(parts)}. {sentence(tested)} Evidence: {cite}", [], cite, absent_video=absent_video)


def standing_not_verified(sub_id, entries, latest, breaks):
    """The newest Not verified record for sub_id that still decides its verdict, or None.

    A later accepted run of a check covering it lifts the record; one written with --until-break also
    needs a later planned break aimed at it.
    """
    own_entries = [entry for entry in entries if entry["sub_feature"] == sub_id]
    if not own_entries:
        return None
    entry = own_entries[-1]
    lifted = latest is not None and str(latest[1].get("finished_at") or "") > entry["at"]
    if entry.get("until") == "break":
        lifted = lifted and any(str(record.get("finished_at") or "") > entry["at"] for _, record in breaks)
    return None if lifted else entry


def not_break_tested_reason(proof):
    """The reason an agent noted on the proof line for a check nobody has broken yet, or None."""
    match = re.search(r"Not break-tested: (.+)$", proof)
    return match.group(1).strip() if match else None


def aimed_breaks(records, sub_id):
    """The accepted planned break runs aimed at sub_id, oldest first."""
    return [(path, record) for path, record in records
            if isinstance(record.get("planned_break"), dict) and sub_id in (record["planned_break"].get("sub_features") or [])]


def latest_break(breaks, record):
    """The newest planned break of the same check as a passing run, or None when none has run."""
    same = [(path, broken) for path, broken in breaks if broken.get("check") == record.get("check")]
    return same[-1] if same else None


def compute_verdicts(harness_dir, seen_ids, proofs, repos):
    """Every mapped behavior's verdict, in map order, as {sub_id: verdict}. A behavior whose proof line is malformed is left out."""
    records = accepted_records(harness_dir / "evidence")
    entries = not_verified_entries(harness_dir)
    return {sub_id: compute_verdict(harness_dir, sub_id, proofs[sub_id], records, entries, repos)
            for sub_id in seen_ids if sub_id in proofs}


def standing_warnings(verdicts, today=None):
    """One warning per behavior a Not verified record still decides, with how long it has stood, so a stale blocker is noticed."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    warnings = []
    for sub_id, computed in verdicts.items():
        entry = computed.get("standing")
        if not entry:
            continue
        try:
            since = datetime.date.fromisoformat(entry["at"][:10])
        except ValueError:
            since = today
        days = max((today - since).days, 0)
        age = "today" if days == 0 else f"{days} day{'' if days == 1 else 's'}"
        lifts = "a new planned break aimed at it" if entry.get("until") == "break" else "a rerun of its check"
        warnings.append(f"{sub_id} has stood Not verified for {age} ({entry['reason']}); {lifts} lifts it")
    return warnings


def render_line(sub_id, computed):
    """One behavior's Latest results line, as status.md carries it."""
    return f"- {sub_id}: {computed['verdict']}. {computed['text']}"


def render_status(harness_dir, verdicts):
    """Write status.md from the computed verdicts, from the evidence on this machine.

    status.md has one owner: this function. Hand-written notes live in notes.md.
    Returns the result lines.
    """
    status = harness_dir / "status.md"
    lines = [render_line(sub_id, computed) for sub_id, computed in verdicts.items()]
    body = ["# Verification status", "", f"## {RESULTS_HEADING}", "", RENDERED_NOTE, ""]
    body += lines or ["No behaviors in the feature map yet."]
    temporary = status.with_name(status.name + ".tmp")
    temporary.write_text("\n".join(body) + "\n")
    temporary.replace(status)
    return lines


def check_status(harness_dir, verdicts, require_evidence, errors, warnings):
    """Every Verified line in status.md's Latest results must be the one vf.py status would write now."""
    status = harness_dir / "status.md"
    if not status.is_file():
        return
    for sub_id, line in latest_result_lines(status.read_text()).items():
        if RESULT.match(line).group(2) != "Verified":
            continue
        label = f"status.md: {sub_id} is Verified"
        cite = EVIDENCE_CITE.search(line)
        if cite and EVIDENCE_PATH.fullmatch(cite.group(1)) and not (harness_dir / cite.group(1)).is_file():
            report_absent(f"{label}, but {cite.group(1)} is not here", require_evidence, errors, warnings)
            continue
        computed = verdicts.get(sub_id)
        if computed is None:
            errors.append(f"{label}, but the map has no sub-feature with that ID")
            continue
        for message in computed["absent_video"]:
            report_absent(f"{label}, but {message}", require_evidence, errors, warnings)
        if computed["verdict"] != "Verified":
            errors.extend(f"{label}, but {problem}" for problem in computed["problems"])
        elif line.strip() != render_line(sub_id, computed):
            errors.append(f"{label}, but the line is not what vf.py status writes now; run it to refresh status.md")


def check_break(harness_dir, sub_id, record, break_run, repos, errors):
    """A planned break proves a sub-feature only when it was aimed at that sub-feature and a step
    judging it failed. Those steps must still be in the Verified run, judging the same sub-feature,
    and every harness file the break ran must be unchanged in the pass. Steps added since only make
    the check stricter. A step that failed only because an earlier one did, such as a receipt step
    after a payment break, earns its own sub-feature nothing."""
    path, broken = break_run
    cite = path.relative_to(harness_dir).as_posix()
    where = f"its planned break in {cite}"
    if broken.get("passed") is not False:
        errors.append(f"{where} did not fail")
    problems = accepted_run_problems(broken, repos)
    if problems:
        errors.extend(f"{where} {problem}" for problem in problems)
        return
    caught = [step["name"] for step in steps_judging(broken, sub_id) if step["passed"] is False]
    if not caught:
        errors.append(f"no step judging it failed in {where}")
    judging = {step["name"] for step in steps_judging(record, sub_id)}
    for name in caught:
        if name not in judging:
            errors.append(f"step '{name}' caught its planned break and does not judge it in this run")
    errors.extend(harness_code_problems(broken, record))


def harness_code_problems(broken, record):
    """Each harness file the planned break ran that the passing run no longer has unchanged.

    A file added since cannot change what an existing check does unless an existing file was edited
    to use it, so additions invalidate nothing. Replaying the saved break clears the problem."""
    before, after = broken.get("harness_code") or {}, record.get("harness_code") or {}
    problems = []
    for name, digest in before.items():
        if name not in after:
            problems.append(f"{name} was removed since its planned break; replay the break with vf.py break replay")
        elif after[name] != digest:
            problems.append(f"{name} changed since its planned break; replay the break with vf.py break replay")
    return problems


def harness_edited_since_run(harness_dir, record):
    """Each harness file the passing run fingerprinted that differs on disk now.

    A pass vouches only for the check as it ran, so an edit, even one that only loosens a step, waits
    for the next run instead of inheriting this pass. A file no longer on disk is left to that run,
    which cannot use it."""
    manifest = record.get("harness_code")
    if not isinstance(manifest, dict):
        return []
    project = project_root(harness_dir)
    problems = []
    for name, digest in manifest.items():
        path = project / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"{name} changed since this run; rerun its check")
    return problems


def is_seconds(value):
    """Whether a value is a usable time in seconds: a finite number that is not negative, and not a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def check_recording(record, cite, evidence_dir, require_evidence, errors, warnings):
    """Check that a cited run's recording, when it has one, sits inside evidence/ and says when it starts."""
    if "recording" not in record:
        return
    recording = record["recording"]
    video = recording.get("video") if isinstance(recording, dict) else None
    if not isinstance(video, str) or not video or Path(video).is_absolute() or ".." in Path(video).parts:
        errors.append(f"{cite} does not name its recording by a path inside evidence/")
    elif not is_seconds(recording.get("starts_at")):
        errors.append(f"{cite} does not say when its recording starts")
    elif not (evidence_dir / video).is_file():
        report_absent(f"its recording {video} is not here", require_evidence, errors, warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("harness_dir", nargs="?", default=Path(__file__).resolve().parents[2], type=Path)
    parser.add_argument("--require-evidence", action="store_true", help="fail when a Verified line cites a missing evidence file")
    parser.add_argument("--run-help", action="store_true", help="run each tools.md Help command, which must exit 0 quickly")
    parser.add_argument("--written-for", metavar="VERSION", help="the Rules version the calling skill was written for; fails on a mismatch and names the side to update")
    args = parser.parse_args()

    project = project_root(args.harness_dir)
    errors = []
    check_rules(args.harness_dir.resolve(), errors)
    check_written_for(args.harness_dir.resolve(), args.written_for, errors)
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
    mapped = read_map(args.harness_dir, project)
    if mapped is None:
        print(f"STOPPED: no feature index at {args.harness_dir / 'features' / 'README.md'}", file=sys.stderr)
        return 2
    files, seen_ids, proofs, map_errors = mapped
    errors.extend(map_errors)
    check_proofs = command_proofs(proofs)

    result_warnings = []
    verdicts = compute_verdicts(args.harness_dir, seen_ids, proofs, repos)
    check_status(args.harness_dir, verdicts, args.require_evidence, errors, result_warnings)
    result_warnings += standing_warnings(verdicts)

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
