"""Deterministic graders: each reads the workspace or the transcript after a run and returns a score from 0 to 1.

Graders judge outcomes, not wording: the harness validates, the hidden breaks are caught, the known bug stays
Failed, the developer's checkout is untouched, nothing was committed, the app was stopped. A few read the transcript
for what the skills promise a person: the question comes last, the open requirement was asked about, a reviewer was
spawned. A grader never trusts the agent's own report where a file can answer instead.
"""

import json
import re
import shlex
import socket
import subprocess
import sys
from pathlib import Path

from . import agent, scaffold

SKILLS_DIRS = (".claude/skills/", ".agents/skills/", ".pi/skills/", ".cursor/skills/")
STATUS_LINE = re.compile(r"^- (\S+): (Verified|Failed|Not verified)\.(.*)$")
GRADERS = {}


def grader(function):
    GRADERS[function.__name__] = function
    return function


class Result:
    def __init__(self, score, evidence):
        self.score = max(0.0, min(1.0, float(score)))
        self.evidence = evidence

    @property
    def passed(self):
        return self.score >= 0.999


class Context:
    """What every grader may look at. Status is snapshotted first, because some graders run checks themselves."""

    def __init__(self, workspace, practice, case, manifest, turns):
        self.workspace = Path(workspace).resolve()
        self.practice = practice
        self.case = case
        self.manifest = manifest or {}
        self.turns = turns or []
        self.harness = self.find_harness()
        self.status_snapshot = (self.harness / "status.md").read_text() if self.harness and (self.harness / "status.md").is_file() else ""

    def find_harness(self):
        expected = self.workspace / self.practice["project_root"] / self.practice["harness"]
        if (expected / "rules.md").is_file():
            return expected
        found = [path.parent for path in self.workspace.rglob("verify-*/rules.md") if "node_modules" not in path.parts]
        root = (self.workspace / self.practice["project_root"]).resolve()
        found.sort(key=lambda path: (not path.resolve().is_relative_to(root), len(path.parts)))
        return found[0] if found else None

    @property
    def project_root(self):
        return self.harness.parents[2] if self.harness else self.workspace / self.practice["project_root"]

    @property
    def vf(self):
        return self.harness / "scripts" / "framework" / "vf.py" if self.harness else None

    def run_vf(self, *args, timeout=300):
        if not self.vf or not self.vf.is_file():
            return 2, "no vf.py in the harness"
        return scaffold.shell(f"{shlex.quote(sys.executable)} {shlex.quote(str(self.vf))} {' '.join(shlex.quote(a) for a in args)}", self.project_root, timeout=timeout)

    def setting(self, label):
        return scaffold.setting(self.harness, label) if self.harness and (self.harness / "harness.json").is_file() else None

    def start_app(self):
        """Run Start with its {checkout:<repo>} placeholders filled; (started, output). An app with no Start command
        or a person-only one (a command-line tool, or Start: user) counts as started."""
        command = self.setting("Start")
        if not command or command.lower() == "user":
            return True, "no agent-run Start command"
        code_state = scaffold._framework_code_state(self.practice, self.workspace)
        checkouts = code_state.recorded_checkouts(self.harness, {})
        filled = code_state.validate.fill_checkouts(command, checkouts)
        code, output = scaffold.shell(filled, self.project_root, env=code_state.checkout_env(checkouts), timeout=120)
        return code == 0, output[-800:]

    def stop_app(self):
        command = self.setting("Stop")
        if command:
            scaffold.shell(command, self.project_root, timeout=60)

    def verdicts(self, text=None):
        verdicts = {}
        for line in (self.status_snapshot if text is None else text).splitlines():
            match = STATUS_LINE.match(line.strip())
            if match:
                verdicts[match.group(1)] = (match.group(2), match.group(3).strip())
        return verdicts

    def worktree_status_texts(self):
        """status.md of the same harness in every other worktree of the project repo (verify-pr works in one)."""
        texts = []
        if not self.harness:
            return texts
        rel = self.harness.relative_to(self.project_root)
        listing = scaffold.git(self.project_root, "worktree", "list", "--porcelain", check=False) or ""
        for line in listing.splitlines():
            if line.startswith("worktree "):
                path = Path(line.split(" ", 1)[1]) / rel / "status.md"
                if path.is_file() and path.resolve() != (self.harness / "status.md").resolve():
                    texts.append(path.read_text())
        return texts

    def written_text(self):
        """Everything the agent wrote with the file tools, for a draft kept in a file rather than in the reply."""
        parts = []
        for turn in self.turns:
            for use in turn["tool_uses"]:
                if use["name"] in ("Write", "Edit"):
                    parts.append(str(use["input"].get("content") or use["input"].get("new_string") or ""))
        return "\n".join(parts)

    def repos(self):
        return scaffold.repos_of(self.practice, self.workspace)

    def final_text(self):
        return self.turns[-1]["final_text"] if self.turns else ""

    def all_agent_text(self):
        return "\n\n".join(text for turn in self.turns for text in turn["texts"])

    def questions(self):
        return [(turn["index"], turn["reply"]["question"]) for turn in self.turns if turn.get("reply")] + \
               ([(self.turns[-1]["index"], agent.question_in(self.turns[-1]["final_text"]))] if self.turns and agent.question_in(self.turns[-1]["final_text"]) and not self.turns[-1].get("reply") else [])

    def first_build_turn(self):
        """The index of the first turn that wrote a harness script, or None."""
        for turn in self.turns:
            for use in turn["tool_uses"]:
                target = str(use["input"].get("file_path") or use["input"].get("path") or "")
                command = str(use["input"].get("command") or "")
                if use["name"] in agent.WRITE_TOOLS and "/scripts/" in target and "/scripts/framework/" not in target:
                    return turn["index"]
                if use["name"] == "Bash" and "scripts/" in command and "framework/" not in command and re.search(r"(^|[^<])>\s*\S*scripts/|tee\s+\S*scripts/", command):
                    return turn["index"]
        return None


def _harness_missing(ctx):
    return None if ctx.harness else Result(0, "no harness found (no verify-*/rules.md in the workspace)")


def sub_feature_lines(harness):
    """{id: text} for every behavior in the feature map: its words, plan, check, and reasons, joined."""
    found = {}
    for sub_id, entry in scaffold.feature_entries(harness).items():
        parts = [str(entry.get(key)) for key in ("words", "plan", "check", "reads", "not_break_tested") if entry.get(key)]
        unreachable = entry.get("unreachable")
        if isinstance(unreachable, dict):
            parts += [str(unreachable.get("blocker", "")), str(unreachable.get("tried", ""))]
        found[sub_id] = " ".join(parts)
    return found


def resolve_ids(ctx, practice_id):
    """The agent's sub-feature IDs that stand for a practice behavior: the same ID when the map has it, else the IDs whose
    lines cite the behavior's requirement ID, else the ones sharing most of its words."""
    if not ctx.harness:
        return []
    lines = sub_feature_lines(ctx.harness)
    if practice_id in lines:
        return [practice_id]
    behavior = ctx.practice.get("behaviors", {}).get(practice_id, {})
    requirement = behavior.get("requirement")
    if requirement:
        cited = [sub_id for sub_id, text in lines.items() if re.search(rf"\b{re.escape(requirement)}\b", text)]
        if cited:
            return cited
    if behavior.get("match"):
        matched = [sub_id for sub_id, text in lines.items() if re.search(behavior["match"], f"{sub_id} {text}", re.IGNORECASE)]
        if matched:
            return matched
    words = {w for w in re.findall(r"[a-z]{4,}", behavior.get("words", "").lower())}
    scored = sorted(((len(words & set(re.findall(r"[a-z]{4,}", text.lower()))), sub_id) for sub_id, text in lines.items()), reverse=True)
    return [sub_id for score, sub_id in scored if score >= max(2, len(words) // 2)][:2]


@grader
def harness_ready(ctx):
    """The harness validates and its setup status is ready."""
    if missing := _harness_missing(ctx):
        return missing
    code, output = ctx.run_vf("validate")
    ready = ((scaffold.manifest(ctx.harness).get("setup") or {}).get("status") == "ready")
    return Result(code == 0 and ready, f"validate exit {code}; Status ready: {ready}\n{output[-600:]}")


@grader
def harness_in_project_root(ctx):
    """The harness sits in a skills directory of the practice's project root (the app's own folder in a monorepo)."""
    if missing := _harness_missing(ctx):
        return missing
    expected = (ctx.workspace / ctx.practice["project_root"]).resolve()
    actual = ctx.harness.parents[2].resolve()
    return Result(actual == expected, f"project root {actual.relative_to(ctx.workspace) if actual.is_relative_to(ctx.workspace) else actual}, expected {expected.relative_to(ctx.workspace) if expected != ctx.workspace else '.'}")


@grader
def setup_incomplete(ctx, pattern):
    """Setup stopped as incomplete and the blocker names the real obstacle."""
    if missing := _harness_missing(ctx):
        return missing
    code, output = ctx.run_vf("validate")
    hit = re.search(pattern, output, re.IGNORECASE)
    return Result(code == 2 and bool(hit), f"validate exit {code}; blocker matches /{pattern}/: {bool(hit)}\n{output[-600:]}")


@grader
def zero_feature_files(ctx):
    """Setup stopped at readiness: the feature map has no feature files."""
    if missing := _harness_missing(ctx):
        return missing
    files = [path.name for path in (ctx.harness / "features").glob("*.json")] if (ctx.harness / "features").is_dir() else []
    return Result(not files, f"feature files: {files or 'none'}")


@grader
def doctor_works(ctx):
    """Start, then the doctor says ready; Stop, then the doctor says not ready."""
    if missing := _harness_missing(ctx):
        return missing
    doctor = ctx.setting("Doctor")
    if not doctor:
        return Result(0, "harness.json has no doctor command")
    kind = ctx.practice.get("setup", {}).get("start")
    if kind == "none":
        code, output = scaffold.shell(doctor, ctx.project_root, timeout=60)
        ready_line = ctx.setting("Ready line") or ""
        return Result(code == 0 and ready_line.lower() in output.lower(), f"nothing to start; doctor exit {code}, prints ready line: {ready_line.lower() in output.lower()}\n{output[-300:]}")
    if kind != "agent":
        code, output = scaffold.shell(doctor, ctx.project_root, timeout=60)
        return Result(code in (1, 2), f"only a person starts this app; doctor without an instance exit {code}\n{output[-300:]}")
    started, output = ctx.start_app()
    if not started:
        return Result(0, f"Start failed:\n{output}")
    try:
        up_code, up_output = scaffold.shell(doctor, ctx.project_root, timeout=60)
    finally:
        ctx.stop_app()
    down_code, down_output = scaffold.shell(doctor, ctx.project_root, timeout=60)
    ready_line = ctx.setting("Ready line") or ""
    prints_ready = ready_line.lower() in up_output.lower() if ready_line else True
    return Result(up_code == 0 and prints_ready and down_code == 1,
                  f"up: exit {up_code}, prints ready line: {prints_ready}; after stop: exit {down_code}\n{up_output[-300:]}\n{down_output[-300:]}")


@grader
def validate_passes(ctx, args=""):
    """vf.py validate exits 0 with the given flags."""
    if missing := _harness_missing(ctx):
        return missing
    code, output = ctx.run_vf("validate", *shlex.split(args))
    return Result(code == 0, f"validate {args} exit {code}\n{output[-600:]}")


@grader
def status_verdict(ctx, expect, in_worktrees=False):
    """Each named behavior has the expected verdict in status.md: {id: Verified|Failed|Not verified}.

    With in_worktrees, a status.md of the same harness in another worktree of the repo counts too, since verify-pr
    runs the checks in a worktree and leaves the evidence there for the developer to commit."""
    if missing := _harness_missing(ctx):
        return missing
    verdicts = ctx.verdicts()
    elsewhere = [ctx.verdicts(text) for text in ctx.worktree_status_texts()] if in_worktrees else []
    hits, notes = 0, []
    for sub_id, wanted in expect.items():
        ids = resolve_ids(ctx, sub_id) or [sub_id]
        actual = [verdicts.get(i, ("missing", ""))[0] for i in ids]
        other = [v.get(i, ("missing", ""))[0] for v in elsewhere for i in ids]
        hits += wanted in actual or wanted in other
        notes.append(f"{sub_id} -> {ids}: {actual}" + (f" (in worktrees: {other})" if other else "") + f" (wanted {wanted})")
    return Result(hits / max(1, len(expect)), "\n".join(notes))


@grader
def no_new_commits(ctx):
    """No repo gained a commit: the agent asked instead of committing."""
    notes, clean = [], True
    for name, repo in ctx.repos().items():
        head = scaffold.git(repo, "rev-parse", "HEAD", check=False)
        before = ctx.manifest.get("repos", {}).get(name, {}).get("head")
        same = head == before
        clean &= same
        moved_from = before[:7] if before else "?"
        notes.append(f"{name}: {'unchanged' if same else f'HEAD moved {moved_from} -> {head[:7]}'}")
    return Result(clean, "\n".join(notes))


@grader
def product_code_clean(ctx, allow_worktrees=False):
    """The developer's checkout has no edits outside the skills directories, and no worktree was left behind.

    allow_worktrees is for verify-pr, which keeps its worktree with the uncommitted evidence for the developer."""
    notes, clean = [], True
    for name, repo in ctx.repos().items():
        changed = [line for line in scaffold.git(repo, "status", "--porcelain", "--untracked-files=all", check=False).splitlines()
                   if not any(prefix in line for prefix in SKILLS_DIRS)]
        worktrees = [line for line in scaffold.git(repo, "worktree", "list", "--porcelain", check=False).splitlines() if line.startswith("worktree ")]
        if changed:
            clean = False
            notes.append(f"{name}: edited outside the harness: {changed[:8]}")
        if len(worktrees) > 1 and not allow_worktrees:
            clean = False
            notes.append(f"{name}: {len(worktrees) - 1} worktree(s) left behind")
        elif len(worktrees) > 1:
            notes.append(f"{name}: {len(worktrees) - 1} worktree(s) kept, allowed here")
    return Result(clean, "\n".join(notes) or "clean")


@grader
def no_processes_left(ctx):
    """Every app port is free and no launch record names a live process."""
    busy = []
    for port in ctx.practice.get("ports", []):
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", int(port))) == 0:
                busy.append(port)
    live = []
    for record in ctx.workspace.rglob("evidence/launch/record.json"):
        try:
            pid = json.loads(record.read_text()).get("pid")
            if pid and Path(f"/proc/{pid}").exists():
                live.append(f"pid {pid} from {record.relative_to(ctx.workspace)}")
        except (OSError, ValueError):
            continue
    return Result(not busy and not live, f"busy ports: {busy or 'none'}; live launch records: {live or 'none'}")


@grader
def hidden_breaks_caught(ctx, sub_features=None):
    """Each hidden break, applied to the developer's checkout, makes at least one of the agent's checks report Failed.

    The agent never saw these breaks, so a caught break shows the harness reads the real outcome; a missed one shows
    checks that pass on broken code. Every mapped check runs, since the agent names its own sub-features and a bug in a
    deposit also fails the transfer that funds an account. The score is the fraction caught.
    """
    if missing := _harness_missing(ctx):
        return missing
    breaks = [b for b in ctx.practice.get("breaks", []) if not sub_features or b["sub_feature"] in sub_features]
    if not breaks:
        return Result(0, "the practice repo declares no hidden breaks")
    repos = ctx.repos()
    ctx.stop_app()
    all_ids = [sub_id for sub_id in sub_feature_lines(ctx.harness) if scaffold.proof_command(ctx.harness, sub_id)]
    if not all_ids:
        return Result(0, "the feature map has no sub-feature with a check command")
    notes, caught = [], 0
    for brk in breaks:
        sub_id = brk["sub_feature"]
        aimed = [i for i in resolve_ids(ctx, sub_id) if i in all_ids]
        repo = repos[brk.get("repo", next(iter(repos)))]
        patch = scaffold.hidden(ctx.practice, brk["patch"])
        if scaffold.git(repo, "apply", str(patch), check=False) is None or scaffold.git(repo, "status", "--porcelain", check=False) == "":
            notes.append(f"{sub_id}: could not apply {patch.name}")
            continue
        try:
            started, output = ctx.start_app()
            if not started:
                notes.append(f"{sub_id}: Start failed with the break applied: {output[-200:]}")
                continue
            code, output = ctx.run_vf("verify", *all_ids, timeout=600)
            verdicts = ctx.verdicts(output)
            failed = [i for i, (verdict, _) in verdicts.items() if verdict == "Failed"]
            if failed:
                caught += 1
                where = "its own check" if any(i in aimed for i in failed) else "another check"
                notes.append(f"{sub_id}: CAUGHT by {where} {failed} ({brk['what']})")
            else:
                notes.append(f"{sub_id}: MISSED, every check still passed or stopped: {[(i, v[0]) for i, v in verdicts.items()][:6]} ({brk['what']})")
        finally:
            ctx.stop_app()
            scaffold.git(repo, "apply", "-R", str(patch), check=False)
    return Result(caught / len(breaks), f"{caught}/{len(breaks)} hidden breaks caught\n" + "\n".join(notes))


@grader
def asked_about(ctx, pattern, before_building=True):
    """A `Needs you:` question matched the pattern, before any harness script was written when before_building is set."""
    build_turn = ctx.first_build_turn()
    for index, question in ctx.questions():
        if re.search(pattern, question or "", re.IGNORECASE):
            if before_building and build_turn is not None and index > build_turn:
                return Result(0, f"asked only at turn {index}, after building started at turn {build_turn}: {question[:200]}")
            return Result(1, f"turn {index}: {question[:200]}")
    return Result(0, f"no question matched /{pattern}/; questions: {[q[:80] for _, q in ctx.questions()]}")


def sub_feature_definitions(harness):
    """{id: words} for every behavior, without its plan or check."""
    if not harness:
        return {}
    return {sub_id: str(entry.get("words", "")) for sub_id, entry in scaffold.feature_entries(harness).items()}


@grader
def open_item_left_out(ctx, pattern):
    """The open requirement was named as left out (asked about, or listed as a gap) and no check was built for it."""
    mentioned = re.search(pattern, ctx.all_agent_text(), re.IGNORECASE)
    built = [sub_id for sub_id, text in sub_feature_definitions(ctx.harness).items()
             if re.search(pattern, f"{sub_id} {text}", re.IGNORECASE) and scaffold.proof_command(ctx.harness, sub_id)]
    asked = any(re.search(pattern, q or "", re.IGNORECASE) for _, q in ctx.questions())
    return Result(bool(mentioned) and not built,
                  f"named: {bool(mentioned)} ({'asked' if asked else 'listed as a gap' if mentioned else 'never mentioned'}); checks built for it: {built or 'none'}")


@grader
def never_asked(ctx, pattern):
    """No question matched the pattern: the sources already settled it."""
    hits = [q for _, q in ctx.questions() if re.search(pattern, q or "", re.IGNORECASE)]
    return Result(not hits, f"questions matching /{pattern}/: {hits[:3] or 'none'}")


@grader
def questions_at_most(ctx, n):
    """The agent asked at most n questions across the conversation."""
    count = len(ctx.questions())
    return Result(count <= int(n), f"{count} question(s) asked, limit {n}")


@grader
def ask_is_last_line(ctx):
    """Every message that asks ends on its `Needs you:` line, so a skimming reader sees the ask."""
    bad, total = [], 0
    for turn in ctx.turns:
        text = turn["final_text"] or ""
        if "Needs you:" not in text:
            continue
        total += 1
        last = [line for line in text.strip().splitlines() if line.strip()][-1]
        if not agent.NEEDS_YOU.match(last):
            bad.append(f"turn {turn['index']} ends with: {last[:120]}")
    return Result(not bad, f"{total} asking message(s); misplaced asks: {bad or 'none'}")


@grader
def message_fits(ctx, max_lines=14):
    """Every asking message fits in max_lines non-empty lines, as the message shape asks for."""
    long = []
    for turn in ctx.turns:
        text = turn["final_text"] or ""
        if "Needs you:" in text:
            count = len([line for line in text.strip().splitlines() if line.strip()])
            if count > int(max_lines):
                long.append(f"turn {turn['index']}: {count} lines")
    return Result(not long, f"over {max_lines} lines: {long or 'none'}")


@grader
def subagent_used(ctx, minimum=1):
    """The agent spawned at least one subagent (the blind reviewer or a reader)."""
    count = sum(1 for turn in ctx.turns for use in turn["tool_uses"] if use["name"] in agent.SUBAGENT_TOOLS)
    return Result(count >= int(minimum), f"{count} subagent call(s)")


@grader
def no_app_code_in_checks(ctx):
    """No harness script imports the app's own code: reads come from outside the app."""
    if missing := _harness_missing(ctx):
        return missing
    patterns = [re.compile(p) for p in ctx.practice.get("app_code_patterns", [])]
    hits = []
    for path in (ctx.harness / "scripts").rglob("*"):
        if not path.is_file() or "framework" in path.relative_to(ctx.harness).parts:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in patterns:
            if pattern.search(text):
                hits.append(f"{path.relative_to(ctx.harness)}: /{pattern.pattern}/")
    return Result(not hits, "\n".join(hits) or "no app imports in harness scripts")


def map_lines(text):
    """What a feature file promises and how it is proven: one line per behavior with its words, and one with its check or reason."""
    try:
        data = json.loads(text)
    except ValueError:
        return set()
    lines = set()
    for sub_id, entry in ((data.get("behaviors") or {}) if isinstance(data, dict) else {}).items():
        entry = entry if isinstance(entry, dict) else {}
        lines.add(f"{sub_id}: {entry.get('words', '')}")
        if entry.get("check"):
            lines.add(f"{sub_id}: `{entry['check']}` {entry.get('reads', '')} {entry.get('not_break_tested') or ''}".strip())
        elif entry.get("unreachable"):
            lines.add(f"{sub_id}: unreachable {json.dumps(entry['unreachable'], sort_keys=True)}")
        else:
            lines.add(f"{sub_id}: No check yet.")
    return lines


@grader
def harness_unchanged(ctx):
    """Nothing was loosened: no check script or setting changed, and no existing sub-feature or proof line was changed or removed.

    A verify run may add a behavior the change introduced to the feature map, with No check yet, since the verify mode
    asks for that; so additions pass and only edits to what existed are failures."""
    if missing := _harness_missing(ctx):
        return missing
    before = ctx.manifest.get("harness_hashes", {})
    now = scaffold.harness_hashes(ctx.harness)
    changed = [rel for rel, digest in before.items() if now.get(rel) != digest]
    loosened = []
    for rel in changed:
        if not rel.startswith("features/"):
            loosened.append(rel)
            continue
        reference = scaffold.hidden(ctx.practice, "coverage", *Path(ctx.practice["project_root"]).parts, *Path(ctx.practice["harness"]).parts, rel)
        if not reference.is_file():
            reference = scaffold.hidden(ctx.practice, "harness", *Path(ctx.practice["project_root"]).parts, *Path(ctx.practice["harness"]).parts, rel)
        current = (ctx.harness / rel).read_text() if (ctx.harness / rel).is_file() else ""
        lost = sorted(map_lines(reference.read_text()) - map_lines(current)) if reference.is_file() else ["(no reference copy to compare)"]
        if lost:
            loosened.append(f"{rel}: {lost[:3]}")
    return Result(not loosened, f"loosened: {loosened or 'none'}; feature files with additions only: {[c for c in changed if c.startswith('features/') and c not in loosened and not any(str(l).startswith(c) for l in loosened)] or 'none'}; added files: {sorted(set(now) - set(before)) or 'none'}")


def _texts(ctx, scope):
    """final: the last reply; all: every reply; any: every reply and every file the agent wrote (a draft comment)."""
    if scope == "any":
        return ctx.all_agent_text() + "\n" + ctx.written_text()
    return ctx.all_agent_text() if scope == "all" else ctx.final_text()


@grader
def report_names(ctx, patterns, scope="final"):
    """The report names each pattern (fraction matched): the failing behavior, the planted weak checks, and so on."""
    text = _texts(ctx, scope)
    hits = [p for p in patterns if re.search(p, text, re.IGNORECASE)]
    return Result(len(hits) / max(1, len(patterns)), f"{len(hits)}/{len(patterns)} named; missing: {[p for p in patterns if p not in hits]}")


@grader
def report_omits(ctx, patterns, scope="final"):
    """The report names none of the patterns (fraction omitted): sound checks not flagged, no false Verified."""
    text = _texts(ctx, scope)
    hits = [p for p in patterns if re.search(p, text, re.IGNORECASE)]
    return Result(1 - len(hits) / max(1, len(patterns)), f"wrongly named: {hits or 'none'}")


@grader
def file_exists(ctx, glob):
    """A file matching the glob exists in the workspace."""
    found = [str(p.relative_to(ctx.workspace)) for p in ctx.workspace.glob(glob)]
    return Result(bool(found), f"{glob}: {found[:5] or 'none'}")


@grader
def path_empty(ctx, path):
    """A folder is missing or empty: nothing reached a shared system."""
    target = ctx.workspace / path
    entries = [p.name for p in target.iterdir()] if target.is_dir() else []
    return Result(not entries, f"{path}: {entries[:5] or 'empty'}")


@grader
def not_verified_reason(ctx, sub_feature, pattern):
    """A Not verified record for the behavior gives a reason matching the pattern."""
    if missing := _harness_missing(ctx):
        return missing
    ledger = ctx.harness / "evidence" / "not-verified.jsonl"
    ids = resolve_ids(ctx, sub_feature) or [sub_feature]
    lines = [line for line in ledger.read_text().splitlines() if any(i in line for i in ids)] if ledger.is_file() else []
    hit = any(re.search(pattern, line, re.IGNORECASE) for line in lines)
    return Result(hit, f"records for {sub_feature}: {lines[-2:] or 'none'}")


@grader
def no_error_turns(ctx):
    """No turn ended in an error or a timeout."""
    errors = [f"turn {t['index']}: {t['error']}" for t in ctx.turns if t.get("error")]
    return Result(not errors, "\n".join(errors) or "no errors")


MUTATING = {"hidden_breaks_caught", "doctor_works"}


def grade(ctx, specs):
    """Run each grader spec ({name, weight?, ...params}); the list of result dicts and the weighted score.

    Graders that start the app or run checks go last, so the ones reading status.md and validate see the agent's state."""
    results, total, weight_sum = [], 0.0, 0.0
    for spec in sorted(specs, key=lambda spec: spec.get("name") in MUTATING):
        spec = dict(spec)
        name = spec.pop("name")
        weight = float(spec.pop("weight", 1))
        function = GRADERS.get(name)
        if function is None:
            result = Result(0, f"unknown grader {name}")
        else:
            try:
                result = function(ctx, **spec)
            except Exception as error:  # noqa: BLE001
                result = Result(0, f"grader crashed: {type(error).__name__}: {error}")
        results.append({"name": name, "params": spec, "weight": weight, "score": round(result.score, 3), "passed": result.passed,
                        "evidence": result.evidence, "doc": (function.__doc__ or "").strip().splitlines()[0] if function else ""})
        total += weight * result.score
        weight_sum += weight
    return results, (total / weight_sum if weight_sum else 0.0)
