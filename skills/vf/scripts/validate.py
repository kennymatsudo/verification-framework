#!/usr/bin/env python3
"""Validate a verification harness's manifest, feature map, and rendered results against their format, the repo, and the evidence.

Usage: validate.py [HARNESS_DIR] [--require-evidence] [--run-help]

HARNESS_DIR defaults to the harness this script sits in, at scripts/framework/. The harness's
rules.md must match the hash vf.py sync recorded for it in scripts/framework/framework.sha256,
so an edited copy, or one from another framework version, fails before anything else. Exits 0 when the
harness is valid, 1 when it has errors, 2 when it cannot run. Evidence age is reported as
warnings only; evidence retention and Git tracking belong to the team.

Everything a script reads is in two kinds of JSON file: harness.json (setup, requirements source, repos,
commands, tools) and one features/<slug>.json per feature (its behaviors, each with its check or the reason
there is none). notes.md is free prose. status.md is written by `vf.py status` and tools.md by `vf.py tools`,
never by hand: a Verified line that `status` would not write now, or a tools.md that `tools` would not write
now, is an error. A behavior is Verified only when its latest accepted run passed against a ready app, an
accepted planned break of the same check aimed at it failed a step judging it after every earlier failed
step judged one of its targets, every step that caught the break still judges it in the passing run, every harness file the break ran is unchanged in the pass, and no
`vf.py not-verified` record written after that run stands. A cited file that is absent is a warning, since a
fresh checkout may not carry evidence; pass --require-evidence right after recording results to make it an
error. An incomplete setup exits 2 with its recorded blocker and next action. --run-help runs each tool's
`<command> --help`, which must exit 0 within 10 seconds. A token, cookie, password, or key written into
harness.json or a harness script is an error: tools read credentials from the project's connection settings.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Written by vf.py sync: the SHA-256 of every framework file it copied, so an edit made since shows.
FRAMEWORK_LOCK = Path("scripts") / "framework" / "framework.sha256"
RULES_VERSION_LINE = re.compile(r"^Rules version: (\S+)$", re.MULTILINE)
ACCEPTED_BY = "vf.py run"
# Start may name a repo's checkout, which vf fills with the developer's checkout or a planned break's scratch copy.
CHECKOUT_PLACEHOLDER = re.compile(r"\{checkout:([a-z0-9][a-z0-9_-]*)\}")
# Start's two words: nothing to start, so each check runs the code VERIFY_CHECKOUT_<REPO> names; or only a person starts the app.
START_NONE = "none"
START_USER = "user"
RELOADS = ("yes", "no")
SHA256 = re.compile(r"[0-9a-f]{64}")
# The manifest: everything a script reads about the app, its repos, its commands, and its tools.
MANIFEST = "harness.json"
SUB_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")
REPO_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
# A template blank left in a value: `<` followed by a lowercase letter.
UNFILLED = re.compile(r"<[a-z]")
SETUP_TEXT = ("target", "findings", "looked_in")
COMMANDS = ("start", "stop", "doctor", "ready_line")
TOOL_REQUIRED = ("command", "use_when", "permissions", "limits")
TOOL_OPTIONAL = ("inputs", "environment", "result", "failure")
RESULT = re.compile(r"^- ([a-z0-9][a-z0-9._-]*): (Verified|Failed|Not verified)\b")
RESULTS_HEADING = "Latest results"
RENDERED_NOTE = ("Written by `vf.py status` from the evidence on this machine; every accepted run refreshes it, "
                 "and `vf.py not-verified` records a check that could not run. Edits here are overwritten; "
                 "notes belong in notes.md.")
RENDERED_TOOLS_NOTE = ("Written by `vf.py tools` from the tools in harness.json; edit the entry there and run it again. "
                       "A read reports current state; it does not by itself prove a feature works.")
# Not verified records agents write with vf.py not-verified, one JSON object per line.
NOT_VERIFIED_LOG = Path("evidence") / "not-verified.jsonl"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
EVIDENCE_CITE = re.compile(r"Evidence: `?([^\s`]+\.json)`?")
# One folder per check keeps evidence/ browsable as runs pile up; rules.md fixes the layout.
EVIDENCE_PATH = re.compile(r"evidence/[^/]+/[^/]+\.json")
ENV_LOCATOR = re.compile(r"^env:([^:]+):([A-Za-z_][A-Za-z0-9_]*)$")
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


def behavior_kind(entry):
    """What a behavior's entry offers: command (it has a check), unreachable, or none."""
    if not isinstance(entry, dict):
        return "none"
    if entry.get("check"):
        return "command"
    if entry.get("unreachable"):
        return "unreachable"
    return "none"


def read_json(path):
    """The JSON object a file holds, or None when the file is missing, unreadable, or holds something else."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def manifest(harness_dir):
    """The harness's harness.json as a dict, or None when it is missing or not a JSON object."""
    return read_json(harness_dir / MANIFEST)


def command(harness_dir, key):
    """A command from harness.json's commands, or None when the manifest or the command is missing or blank."""
    data = manifest(harness_dir)
    commands = (data or {}).get("commands")
    value = commands.get(key) if isinstance(commands, dict) else None
    if isinstance(value, bool):
        return value
    return value.strip() if isinstance(value, str) and value.strip() else None


def unreachable_text(entry):
    """The Unreachable sentence status.md carries for a behavior with no route to a check."""
    block = entry.get("unreachable") or {}
    return f"Unreachable: {str(block.get('blocker', '')).rstrip('.')}. Tried {str(block.get('tried', '')).rstrip('.')}."


def checkout_placeholders(command):
    """The repo names a command's {checkout:<repo>} placeholders stand for, in order, each once."""
    return list(dict.fromkeys(CHECKOUT_PLACEHOLDER.findall(command or "")))


def fill_checkouts(command, checkouts):
    """The command with each {checkout:<repo>} replaced by that repo's checkout path, shell-quoted; ValueError for a repo not in checkouts."""
    def fill(match):
        name = match.group(1)
        if name not in checkouts:
            raise ValueError(f"{{checkout:{name}}}: no checkout for {name} here, or harness.json does not list it")
        return shlex.quote(str(checkouts[name]))
    return CHECKOUT_PLACEHOLDER.sub(fill, command)


CHECKS_FOLDER = "checks"


def normalized(content):
    """Bytes with CRLF line endings turned to LF, so a Git checkout's conversion is not an edit."""
    return content.replace(b"\r\n", b"\n")


def file_fingerprint(path):
    """SHA-256 of a harness file's content with line endings normalized."""
    return hashlib.sha256(normalized(path.read_bytes())).hexdigest()


def harness_code(harness_dir, command=()):
    """The harness's own code as {path from the project root: fingerprint}: harness.json, every file under
    scripts/ apart from the framework copies, and any file the check command names. A planned break and a
    later pass must agree on it.

    Under scripts/checks/ each top-level entry, a file or a folder, is one check's own code, so only the
    entries the command names count; the rest belong to checks this command cannot load. A command that
    names nothing under checks/ gets all of it, since the check it runs could be any of them."""
    project = project_root(harness_dir)
    scripts = harness_dir / "scripts"
    checks = scripts / CHECKS_FOLDER
    named = [project / word for word in command
             if "/" in word and "\n" not in word and not word.startswith("-") and len(word) < 1024 and (project / word).is_file()]
    named_checks = {check_entry(checks, path) for path in named} - {None}
    files = list(named)
    if (harness_dir / MANIFEST).is_file():
        files.append(harness_dir / MANIFEST)
    for path in scripts.rglob("*") if scripts.is_dir() else ():
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        top = path.relative_to(scripts).parts[0]
        if top == "framework" or (top == CHECKS_FOLDER and named_checks and check_entry(checks, path) not in named_checks):
            continue
        files.append(path)
    manifest = {}
    for path in files:
        try:
            key = path.resolve().relative_to(project.resolve()).as_posix()
        except ValueError:
            continue
        manifest[key] = file_fingerprint(path)
    return dict(sorted(manifest.items()))


def check_entry(checks, path):
    """The top-level file or folder under scripts/checks/ that holds path, or None when path is outside it."""
    try:
        return path.resolve().relative_to(checks.resolve()).parts[0]
    except (ValueError, IndexError):
        return None


def command_path_exists(command, project):
    """Whether a proof command's program exists, when it is named by a path from the project root."""
    first = command.split()[0]
    if "/" not in first:
        return True
    return (project / first).exists()


def unfilled(value):
    """Whether a string still holds a template blank."""
    return isinstance(value, str) and bool(UNFILLED.search(value))


def text_field(data, key, label, errors, required=True, slots=True):
    """A non-empty string field, and with slots set one without a template blank; an error otherwise. Returns the value or None.

    Prose fields that describe a tool may legitimately write `<id>` or `<reason>`, so they pass slots=False."""
    value = data.get(key)
    if value is None or value == "":
        if required:
            errors.append(f"{label}: {key} is missing")
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {key} must be a non-empty string")
        return None
    if slots and unfilled(value):
        errors.append(f"{label}: {key} still has an unfilled slot: {value}")
        return None
    return value.strip()


def string_list(data, key, label, errors):
    """An optional list of strings; an error when it is something else. Returns the list."""
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{label}: {key} must be a list of strings")
        return []
    return value


def check_feature(path, project, repos, seen_ids, errors):
    """Check one features/<slug>.json: its name and summary, and each behavior's entry, adding its IDs to seen_ids.

    Returns each well-formed behavior's entry, in file order, with "feature" set to the file's name.
    """
    name = path.name
    data = read_json(path)
    if data is None:
        errors.append(f"{name}: not a JSON object")
        return {}
    text_field(data, "name", name, errors)
    text_field(data, "summary", name, errors)
    for key in ("reach", "sources", "gotchas"):
        string_list(data, key, name, errors)
    behaviors = data.get("behaviors")
    if not isinstance(behaviors, dict):
        errors.append(f"{name}: behaviors must be an object of <id>: <entry>")
        return {}
    well_formed = {}
    for sub_id, entry in behaviors.items():
        label = f"{name}: {sub_id}"
        if not SUB_ID.fullmatch(sub_id):
            errors.append(f"{label}: an ID is lowercase letters, digits, dots, dashes, and underscores")
            continue
        if sub_id in seen_ids:
            errors.append(f"{label}: also defined in {seen_ids[sub_id]}")
        seen_ids[sub_id] = name
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be an object")
            continue
        text_field(entry, "words", label, errors)
        text_field(entry, "plan", label, errors, required=False)
        check = entry.get("check")
        unreachable = entry.get("unreachable")
        if check is not None and (not isinstance(check, str) or not check.strip()):
            errors.append(f"{label}: check must be a command or null")
            continue
        if check and unfilled(check):
            errors.append(f"{label}: check still has an unfilled slot: {check}")
            continue
        if check:
            if not command_path_exists(check, project):
                errors.append(f"{label}: check names `{check}`, but {check.split()[0]} does not exist")
            text_field(entry, "reads", label, errors)
            if unreachable:
                errors.append(f"{label}: has both a check and an unreachable reason")
        else:
            if "reads" in entry and entry["reads"] is not None:
                errors.append(f"{label}: reads belongs with a check")
            if entry.get("not_break_tested"):
                errors.append(f"{label}: not_break_tested belongs with a check")
            if unreachable is not None:
                if not isinstance(unreachable, dict):
                    errors.append(f"{label}: unreachable must be {{\"blocker\": ..., \"tried\": ...}}")
                    continue
                else:
                    text_field(unreachable, "blocker", f"{label} unreachable", errors)
                    text_field(unreachable, "tried", f"{label} unreachable", errors)
        text_field(entry, "not_break_tested", label, errors, required=False)
        for key in entry:
            if key not in ("words", "plan", "check", "reads", "repos", "not_break_tested", "unreachable"):
                errors.append(f"{label}: unknown field {key}")
        named = entry.get("repos")
        if named is not None:
            if not isinstance(named, list) or not named or not all(isinstance(item, str) for item in named):
                errors.append(f"{label}: repos must be a non-empty list of repo names")
            else:
                for repo in named:
                    if repo not in repos:
                        errors.append(f"{label}: repos names {repo}, which is not a repo in harness.json")
        well_formed[sub_id] = dict(entry, feature=name)
    return well_formed


def command_proofs(behaviors):
    """The behaviors that have a check."""
    return {sub_id: entry for sub_id, entry in behaviors.items() if behavior_kind(entry) == "command"}


def behavior_repos(entry, repos):
    """The repos a behavior's check runs, which its records must cover: its repos list, else every repo in harness.json."""
    named = entry.get("repos") if isinstance(entry, dict) else None
    return list(named) if named else list(repos)


def read_map(harness_dir, project, repos=None):
    """Read and check the feature map: every features/<slug>.json, in name order.

    Returns (feature file names, behavior IDs in map order with their file, each behavior's entry, errors). A harness
    with no features/ folder has an empty map: Git keeps no empty folder, so a harness with no feature yet has none.
    """
    features_dir = harness_dir / "features"
    if repos is None:
        repos = (manifest(harness_dir) or {}).get("repos") or {}
    errors = []
    files = {p.name for p in features_dir.glob("*.json")} if features_dir.is_dir() else set()
    seen_ids, behaviors = {}, {}
    for name in sorted(files):
        behaviors.update(check_feature(features_dir / name, project, repos, seen_ids, errors))
    return files, seen_ids, behaviors, errors


def check_repos(repos, errors):
    """harness.json's repos: a non-empty object of valid names to portable locators. Returns it, or {} when malformed."""
    if not isinstance(repos, dict) or not repos:
        errors.append("harness.json: repos must be a non-empty object of <name>: <locator>")
        return {}
    for name, locator in repos.items():
        if not REPO_NAME.fullmatch(name):
            errors.append(f"harness.json: repo name {name!r} is not lowercase letters, digits, dashes, and underscores")
        if not isinstance(locator, str) or not locator:
            errors.append(f"harness.json: {name} needs a locator")
        elif locator.startswith("env:") and not ENV_LOCATOR.match(locator):
            errors.append(f"harness.json: invalid locator for {name}")
        elif unfilled(locator):
            errors.append(f"harness.json: {name} has an unfilled repo locator")
        elif Path(locator).is_absolute() or locator.startswith("~"):
            errors.append(f"harness.json: {name} locator must be portable")
    return {name: locator for name, locator in repos.items() if isinstance(locator, str)}


def check_manifest(harness_dir, errors):
    """Check harness.json's app, requirements, repos, commands, and tools, and that the harness's fixed files exist.
    Returns the repos by name."""
    data = manifest(harness_dir)
    if data is None:
        errors.append("harness.json is missing or is not a JSON object")
        return {}
    text_field(data, "app", "harness.json", errors)
    requirements = data.get("requirements")
    if requirements is not None and (not isinstance(requirements, str) or unfilled(requirements)):
        errors.append("harness.json: requirements must be a source, or null")
    repos = check_repos(data.get("repos"), errors)
    commands = data.get("commands")
    if not isinstance(commands, dict):
        errors.append("harness.json: commands must be an object")
        commands = {}
    for key in COMMANDS:
        text_field(commands, key, "harness.json commands", errors)
    probe = commands.get("probe")
    if probe is not None and (not isinstance(probe, str) or not probe.strip() or unfilled(probe)):
        errors.append("harness.json commands: probe must be a command, or null")
    if not isinstance(commands.get("reloads"), bool):
        errors.append("harness.json commands: reloads must be true or false")
    for name in checkout_placeholders(commands.get("start") if isinstance(commands.get("start"), str) else ""):
        if name not in repos:
            errors.append(f"harness.json commands: start names {{checkout:{name}}}, which is not a repo")
    tools = data.get("tools")
    if tools is not None and not isinstance(tools, dict):
        errors.append("harness.json: tools must be an object of <name>: <entry>")
    for filename in ("README.md", "notes.md", "status.md", "tools.md"):
        if not (harness_dir / filename).is_file():
            errors.append(f"{filename} is missing from the harness")
    return repos


def tool_folder(entry, project):
    """The folder a tool runs from: the project root for "." or "the project root", else a folder under it."""
    run_from = entry.get("run_from") or "."
    return project if run_from in (".", "the project root") else project / run_from


def check_tools(harness_dir, project, run_help, errors):
    """Check each tool entry in harness.json, that tools.md is what vf.py tools writes now, and, with run_help, each help command."""
    data = manifest(harness_dir) or {}
    tools = data.get("tools") if isinstance(data.get("tools"), dict) else {}
    for name, entry in tools.items():
        label = f"harness.json tool {name!r}"
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be an object")
            continue
        for key in TOOL_REQUIRED:
            text_field(entry, key, label, errors, slots=key == "command")
        for key in TOOL_OPTIONAL:
            text_field(entry, key, label, errors, required=False, slots=False)
        run_from = entry.get("run_from")
        if run_from is not None and (not isinstance(run_from, str) or not run_from):
            errors.append(f"{label}: run_from must be a folder relative to the project root")
            continue
        for key in entry:
            if key not in TOOL_REQUIRED + TOOL_OPTIONAL + ("run_from",):
                errors.append(f"{label}: unknown field {key}")
        folder = tool_folder(entry, project)
        if not folder.is_dir():
            errors.append(f"{label}: runs from {run_from}, which is not a folder under the project root")
            continue
        command = entry.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        script = next((word for word in command.split() if "/" in word and not word.startswith("-")), None)
        if script and not (folder / script).exists():
            errors.append(f"{label}: {script} does not exist in {run_from or '.'}")
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
    rendered = harness_dir / "tools.md"
    if rendered.is_file() and rendered.read_text() != render_tools(data):
        errors.append("tools.md is not what vf.py tools writes now; run it to refresh tools.md")


def render_tools(data):
    """tools.md as vf.py tools writes it from harness.json: one entry per tool, every field it has, and its help command."""
    tools = data.get("tools") if isinstance(data.get("tools"), dict) else {}
    lines = [f"# {data.get('app') or 'Harness'} tools", "", RENDERED_TOOLS_NOTE, ""]
    if not tools:
        lines.append("No tools yet.")
    for name, entry in tools.items():
        entry = entry if isinstance(entry, dict) else {}
        run_from = entry.get("run_from") or "."
        where = "the project root" if run_from in (".", "the project root") else f"`{run_from}`"
        lines += [f"## {name}", "", f"Use when: {entry.get('use_when', '')}", "", f"Run from {where}:", "", f"`{entry.get('command', '')}`", ""]
        for key, title in (("inputs", "Inputs"), ("environment", "Environment"), ("permissions", "Permissions"),
                           ("result", "Result"), ("failure", "Failure"), ("limits", "Limits")):
            if entry.get(key):
                lines.append(f"- {title}: {entry[key]}")
        lines += ["", f"Help: `{entry.get('command', '')} --help`", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def write_tools(harness_dir):
    """Write tools.md from harness.json through a temporary file; returns the rendered text."""
    text = render_tools(manifest(harness_dir) or {})
    target = harness_dir / "tools.md"
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text)
    temporary.replace(target)
    return text


def credential_errors(harness_dir):
    """Report each line in harness.json or a harness script that holds what looks like a credential, without echoing it."""
    scripts = harness_dir / "scripts"
    files = [harness_dir / MANIFEST]
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
        errors.append("rules.md differs from the copy vf last synced; run vf to update or restore it, and put app specifics in harness.json")


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
    """Check harness.json's setup block: its status, the record setup resumes from, and the proof a ready harness needs.

    Returns the block when setup is incomplete, so the run can stop with its blocker, and None otherwise.
    """
    data = manifest(harness_dir)
    if data is None:
        errors.append("harness.json is missing or is not a JSON object; the harness's settings belong there")
        return None
    setup = data.get("setup")
    if not isinstance(setup, dict):
        errors.append("harness.json: setup must be an object")
        return None
    status = setup.get("status")
    if status not in ("incomplete", "ready"):
        errors.append("harness.json: setup.status must be incomplete or ready")
        return None
    for key in SETUP_TEXT:
        text_field(setup, key, "harness.json setup", errors)
    for key in ("blocker", "next", "doctor_proof"):
        value = setup.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip() or unfilled(value)):
            errors.append(f"harness.json setup: {key} must be text or null")
    if status == "incomplete":
        for key in ("blocker", "next"):
            if not setup.get(key):
                errors.append(f"harness.json setup: incomplete setup needs a {key}")
        return setup
    proof = setup.get("doctor_proof")
    if not proof or str(proof).strip().lower().startswith("not run"):
        errors.append("harness.json setup: ready setup needs doctor_proof")
    for key in ("blocker", "next"):
        if setup.get(key):
            errors.append(f"harness.json setup: ready setup still has a {key}")
    return None


def git(directory, *args):
    """Git's trimmed output in directory, or None when the command fails."""
    result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def project_root(harness_dir):
    """The folder holding the skills directory the harness sits in: `app/` for `app/.agents/skills/verify-app/`.

    Recipe commands run from it, and harness.json's repo locators and env: files resolve from it.
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


# The worktree `vf.py break worktree` made for a harness's repo, by harness path, in the project's private Git
# folder: a run that tests a pull request finds every repo's worktree from the harness copy it runs, though a
# relative locator there still reaches the developer's checkout and an env: locator's file isn't in a fresh
# worktree. It stays out of the working tree and harness.json, so no check's fingerprint moves.
WORKTREES_FILE = "verify-worktrees.json"
# Shared by every copy of this module one process loads, since each script loads its siblings by path,
# so a command announces each recorded worktree once.
ANNOUNCED_WORKTREES = sys.__dict__.setdefault("_verify_announced_worktrees", set())


def worktrees_file(harness_dir):
    """Where the harness's recorded worktrees live: the project's private Git folder, or None outside Git."""
    private = git(project_root(harness_dir), "rev-parse", "--absolute-git-dir")
    return Path(private) / WORKTREES_FILE if private else None


def recorded_worktrees(harness_dir):
    """Every harness's recorded worktrees in this project, {harness path: {repo: path}}; empty when none are recorded."""
    path = worktrees_file(harness_dir)
    try:
        data = json.loads(path.read_text()) if path else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read the worktrees `vf.py break worktree` recorded at {path}: {error}; remove the file") from error
    return data if isinstance(data, dict) else {}


def recorded_worktree(harness_dir, name):
    """The worktree `vf.py break worktree` recorded as the harness's checkout for repo name, or None."""
    try:
        entry = recorded_worktrees(harness_dir).get(str(Path(harness_dir).resolve()))
    except ValueError as error:
        print(f"WARNING: {error}", file=sys.stderr)
        return None
    value = entry.get(name) if isinstance(entry, dict) else None
    return Path(value) if isinstance(value, str) else None


def repo_checkout(harness_dir, name, locator):
    """The checkout for harness.json's repo name: the worktree `vf.py break worktree` recorded for it, else
    the locator's (resolve_repo); None when there is no Git checkout there.

    A recorded worktree is announced on stderr, once per command, so no run uses it unseen."""
    recorded = recorded_worktree(harness_dir, name)
    if recorded is None:
        return resolve_repo(locator, project_root(harness_dir))
    found = bool(git(recorded, "rev-parse", "--show-toplevel"))
    key = (str(Path(harness_dir).resolve()), name, str(recorded))
    if key not in ANNOUNCED_WORKTREES:
        ANNOUNCED_WORKTREES.add(key)
        gone = "" if found else ", which is no longer a Git checkout"
        print(f"{name}: using {recorded}, the worktree `vf.py break worktree` recorded{gone}; "
              f"`vf.py break worktree --clear {name}` goes back to harness.json's locator", file=sys.stderr)
    return recorded if found else None


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
    if tested == head:
        return None
    # After a rebase, commit..HEAD also counts the rebased copies of the tested commits, so the count
    # only means "behind" when the tested commit is still in HEAD's history.
    in_history = subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor", tested, head], capture_output=True)
    if in_history.returncode != 0:
        return f"{name} last pass ran on {tested[:12]}, which is not in HEAD's history (rebased, or another branch)"
    return f"{name} last pass is {behind} commit{'' if behind == '1' else 's'} behind HEAD"


def evidence_warnings(evidence_dir, check_proofs, repos):
    """Warnings about each checked sub-feature's latest passing evidence, and about checkouts with uncommitted code now."""
    latest = latest_passing_records(evidence_dir)
    # Group by message so a stale repo prints once with every sub-feature it affects.
    subs_by_message = {}
    checkouts = {}
    # Many sub-features share a passing run, so the same repo and commit come up hundreds of times, and each
    # lookup runs several git commands that take most of a second in a large repo.
    stale_messages = {}
    for sub_id in sorted(check_proofs):
        record = latest.get(sub_id)
        if not record:
            subs_by_message.setdefault("no passing evidence", []).append(sub_id)
            continue
        code = record.get("code") if isinstance(record.get("code"), dict) else {}
        for name in behavior_repos(check_proofs[sub_id], repos):
            locator = repos.get(name)
            if locator is None:
                continue
            source = code.get(name) if isinstance(code.get(name), dict) else {}
            commit = source.get("commit") if isinstance(source.get("commit"), str) else None
            if name not in checkouts:
                checkouts[name] = repo_checkout(evidence_dir.parent, name, locator)
            checkout = checkouts[name]
            if not checkout:
                subs_by_message.setdefault(f"{name} checkout cannot be found from harness.json", []).append(sub_id)
                continue
            if (name, commit) not in stale_messages:
                stale_messages[(name, commit)] = stale_commit_warning(name, checkout, commit)
            message = stale_messages[(name, commit)]
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
    paths = source_pathspec(checkout, harness_dir)
    # Git skips its untracked-file cache whenever a pathspec is given, which costs seconds in a large repo. At the
    # repo's top level "." is the whole repo, so it can go; in a subfolder it scopes the answer to the app.
    if paths == ["."] and git(checkout, "rev-parse", "--show-prefix") == "":
        paths = []
    result = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain", "--", *paths], capture_output=True, text=True)
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


def break_catch(record, sub_id):
    """How a planned break run caught sub_id: the names of the failed steps judging it, and the first step
    before the earliest of them that failed without judging sub_id, or None.

    The break earns sub_id credit only when it was caught and no such step failed first. A step judging
    sub_id that failed only because an earlier step failed proves nothing, even when that earlier step
    judges another target: skip the order insert, and the payment step fails only because no order
    exists. So one break credits the behavior whose step failed first, and any other behavior that same
    step judges.
    """
    caught, spoiled_by = [], None
    for step in record.get("steps") or []:
        if not isinstance(step, dict) or step.get("passed") is not False:
            continue
        if sub_id in judged_by(step, record):
            caught.append(step.get("name"))
        elif not caught and spoiled_by is None:
            spoiled_by = step.get("name")
    return caught, spoiled_by


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
        elif planned.get("repo") not in repos:
            problems.append("has a planned_break whose repo is not one the behavior's check runs")
    if "ended_early" in record and planned is None:
        problems.append("was ended early by vf.py run but is not a planned break")
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
    if not (isinstance(doctor, dict) and doctor.get("exit_code") == 0):
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
    # `proof` is the behavior's entry from its features/<slug>.json.
    """A behavior's verdict from its entry, the accepted evidence, and the Not verified records.

    Verified needs the latest accepted run of a check covering the behavior to have passed against a
    ready app, the newest accepted planned break of that check aimed at it to have cleanly failed a step
    judging it (break_catch), those steps to still judge it in the passing run, every harness file the break ran to be unchanged,
    every harness file the passing run ran to be unchanged on disk, and no standing Not verified record
    written after the run. Anything less is Failed, when the latest
    run failed, or Not verified with the reason.
    """
    kind = behavior_kind(proof)
    if kind == "none":
        return verdict("Not verified", "No check yet.", ["the map has no check for it"])
    if kind == "unreachable":
        return verdict("Not verified", unreachable_text(proof), ["the map says it is unreachable"])

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
    required = behavior_repos(proof, repos)
    problems = accepted_run_problems(record, required) + harness_edited_since_run(harness_dir, record)
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
        check_break(harness_dir, sub_id, record, broken, required, problems)
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
    """The reason an agent recorded in the behavior's entry for a check nobody has broken yet, or None."""
    reason = proof.get("not_break_tested") if isinstance(proof, dict) else None
    return reason.strip() if isinstance(reason, str) and reason.strip() else None


def aimed_breaks(records, sub_id):
    """The accepted planned break runs aimed at sub_id, oldest first."""
    return [(path, record) for path, record in records
            if isinstance(record.get("planned_break"), dict) and sub_id in (record["planned_break"].get("sub_features") or [])]


def latest_break(breaks, record):
    """The newest planned break of the same check as a passing run, or None when none has run."""
    same = [(path, broken) for path, broken in breaks if broken.get("check") == record.get("check")]
    return same[-1] if same else None


def compute_verdicts(harness_dir, seen_ids, proofs, repos):
    """Every mapped behavior's verdict, in map order, as {sub_id: verdict}. A behavior whose entry is malformed is left out."""
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
    """A planned break proves a sub-feature only when it was aimed at that sub-feature, a step judging
    it failed, and every step that failed before the first of those also judges it, as break_catch decides. Those steps must still be in the Verified run, judging the same sub-feature,
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
    caught, spoiled_by = break_catch(broken, sub_id)
    if not caught:
        errors.append(f"no step judging it failed in {where}")
    elif spoiled_by is not None:
        errors.append(f"step '{spoiled_by}' failed before any step judging it in {where}, so the break did not reach it cleanly; "
                      "plan a break of its own that the earlier steps pass through")
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
        if path.is_file() and file_fingerprint(path) != digest:
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
    parser.add_argument("--run-help", action="store_true", help="run each tool's `<command> --help`, which must exit 0 quickly")
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
        print(f"STOPPED: setup incomplete for {incomplete_setup.get('target')}")
        print(f"Blocker: {incomplete_setup.get('blocker')}")
        print(f"Next action: {incomplete_setup.get('next')}")
        return 2
    repos = check_manifest(args.harness_dir, errors)
    check_tools(args.harness_dir, project, args.run_help, errors)
    errors.extend(credential_errors(args.harness_dir))
    mapped = read_map(args.harness_dir, project, repos)
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
        for warning in evidence_warnings(evidence_dir, check_proofs, repos):
            print(f"WARN {warning}")
    else:
        print(f"WARN no evidence directory at {evidence_dir}")

    total = len(seen_ids)
    print(f"{len(files)} features, {total} sub-features, {len(check_proofs)} with checks, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
