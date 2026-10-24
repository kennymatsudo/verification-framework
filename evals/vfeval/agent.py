"""Drive an agent through a case: one headless Claude Code run per turn, with a simulated developer answering.

The skills pause for a person at `Needs you:` lines. The simulated developer answers each one from the practice
repo's hidden answer sheet: a rule whose pattern matches the question wins, otherwise the sheet's default. With
--user-model, a small model plays the developer from the sheet's persona and facts instead, so a question the
rules did not foresee still gets an answer in character. Either way the answers never reveal the hidden breaks.
"""

import json
import os
import re
import shlex
import subprocess
import time

from . import FRAMEWORK

NEEDS_YOU = re.compile(r"^\s*(?:\*\*)?Needs you:(?:\*\*)?\s*(.*)$", re.MULTILINE)
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SUBAGENT_TOOLS = {"Agent", "Task"}
# Read, Glob, and Grep need a grant for files outside the workspace, such as the plugin's own reference files.
ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Bash", "Edit", "Write", "MultiEdit", "NotebookEdit", "Agent", "Skill", "TodoWrite", "WebFetch"]


class Turn:
    def __init__(self):
        self.session_id = None
        self.final_text = ""
        self.texts = []
        self.tool_uses = []
        self.cost_usd = 0.0
        self.duration_ms = 0
        self.num_turns = 0
        self.error = None
        self.raw = []


def parse_stream(lines, turn):
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            turn.raw.append(line)
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            turn.session_id = event.get("session_id") or turn.session_id
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and block.get("text"):
                    turn.texts.append(block["text"])
                elif block.get("type") == "tool_use":
                    turn.tool_uses.append({"name": block.get("name"), "input": block.get("input", {})})
        elif kind == "result":
            turn.session_id = event.get("session_id") or turn.session_id
            turn.final_text = event.get("result") or (turn.texts[-1] if turn.texts else "")
            turn.cost_usd = event.get("total_cost_usd") or 0.0
            turn.duration_ms = event.get("duration_ms") or 0
            turn.num_turns = event.get("num_turns") or 0
            if event.get("is_error") or event.get("subtype", "success") != "success":
                turn.error = event.get("subtype") or "error"
    if not turn.final_text and turn.texts:
        turn.final_text = turn.texts[-1]
    return turn


def claude_command(prompt, model=None, resume=None, max_turns=60, framework=FRAMEWORK, extra=()):
    command = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--plugin-dir", str(framework),
               "--add-dir", str(framework), "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED_TOOLS,
               "--disallowedTools", "AskUserQuestion", "--max-turns", str(max_turns)]
    if model:
        command += ["--model", model]
    if resume:
        command += ["--resume", resume]
    command += list(extra)
    return command


def run_turn(prompt, cwd, timeout, **kwargs):
    """One headless run; the Turn it produced. A timeout kills the process and records the error."""
    turn = Turn()
    command = claude_command(prompt, **kwargs)
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        lines = result.stdout.splitlines()
        if result.returncode and not lines:
            turn.error = f"claude exited {result.returncode}: {result.stderr.strip()[:500]}"
    except subprocess.TimeoutExpired as expired:
        lines = (expired.stdout or b"").decode(errors="replace").splitlines() if isinstance(expired.stdout, bytes) else (expired.stdout or "").splitlines()
        turn.error = f"timed out after {timeout}s"
    parse_stream(lines, turn)
    if not turn.duration_ms:
        turn.duration_ms = int((time.monotonic() - started) * 1000)
    return turn


def question_in(text):
    """The last `Needs you:` question in a message, or None when it asks nothing."""
    found = NEEDS_YOU.findall(text or "")
    return found[-1].strip() if found else None


def answer_from_rules(sheet, question, full_text):
    for rule in sheet.get("rules", []):
        pattern = re.compile(rule["pattern"], re.IGNORECASE)
        if pattern.search(question or "") or (rule.get("anywhere") and pattern.search(full_text or "")):
            return rule["answer"], f"rule /{rule['pattern']}/"
    return sheet.get("default", "Go ahead."), "default"


def answer_from_model(sheet, message, model, timeout=120):
    """Ask a small model to answer as the developer, from the sheet's persona and facts only."""
    prompt = "\n".join([
        sheet.get("persona", "You are the app's developer."),
        "Facts you know (answer only from these; if they do not cover the question, say you don't know and tell the agent to use its judgment without inventing requirements):",
        *[f"- {fact}" for fact in sheet.get("facts", [])],
        "", "The agent working for you wrote this message:", "---", message, "---",
        "Reply to its question in one or two short sentences, as the developer, with no preamble.",
    ])
    command = ["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
               "--disallowedTools", "Bash", "Read", "Edit", "Write", "Agent", "Skill", "Glob", "Grep", "WebFetch", "WebSearch"]
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        data = json.loads(result.stdout)
        text = (data.get("result") or "").strip()
        return (text or sheet.get("default", "Go ahead.")), f"user model {model}"
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return sheet.get("default", "Go ahead."), "default (user model failed)"


def converse(prompt, cwd, sheet, max_user_turns=6, user_model=None, **kwargs):
    """Run the case as a conversation; the list of turns, each with the agent's run and the developer's reply."""
    turns = []
    session = None
    message = prompt
    for index in range(max_user_turns + 1):
        turn = run_turn(message, cwd, resume=session, **kwargs)
        session = turn.session_id or session
        record = {"index": index, "prompt": message, "final_text": turn.final_text, "texts": turn.texts,
                  "tool_uses": turn.tool_uses, "cost_usd": turn.cost_usd, "duration_ms": turn.duration_ms,
                  "num_turns": turn.num_turns, "error": turn.error, "session_id": turn.session_id, "reply": None}
        turns.append(record)
        question = question_in(turn.final_text)
        if turn.error or question is None or index == max_user_turns:
            break
        if user_model:
            reply, source = answer_from_model(sheet, turn.final_text, user_model)
        else:
            reply, source = answer_from_rules(sheet, question, turn.final_text)
        record["reply"] = {"question": question, "answer": reply, "source": source}
        message = reply
    return turns


def transcript_lines(turns):
    """A readable transcript for a results folder."""
    lines = []
    for turn in turns:
        lines.append(f"## Developer\n\n{turn['prompt']}\n")
        for use in turn["tool_uses"]:
            summary = json.dumps(use["input"])[:160]
            lines.append(f"- tool {use['name']}: {summary}")
        lines.append(f"\n## Agent (turn {turn['index']}, {turn['num_turns']} steps, ${turn['cost_usd']:.2f})\n\n{turn['final_text']}\n")
        if turn["error"]:
            lines.append(f"ERROR: {turn['error']}\n")
    return "\n".join(lines)
