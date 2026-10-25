#!/usr/bin/env python3
"""Start, stop, and check an app instance the harness launched, with a launch record naming the code it loaded.

Usage:
  launch.py start [--until COMMAND] [--timeout SECONDS] [--checkout NAME=PATH ...] -- COMMAND...
  launch.py stop
  launch.py doctor [--probe COMMAND]
  launch.py status

--harness DIR picks the harness; it defaults to the one this script sits in, at scripts/framework/.

start records every repo's code state (code_state.py, with any --checkout override), runs COMMAND from the
project root as its own process group with its output in evidence/launch/output.log, and writes
evidence/launch/record.json: the command, the process ID, when it started, the code state, and the
overrides. It refuses while a record names a process that is still running; a record whose process has
exited is replaced, so a crash or reboot never blocks the next start. With --until, it polls that shell
command until it exits 0 and then prints `started`; when the process exits first or --timeout seconds
(default 60) pass, it stops the process, removes the record, and exits 1 with the log's last lines.

stop sends the recorded process group SIGTERM, waits up to 10 seconds, then SIGKILL, and removes the
record. With no record it prints `nothing to stop` and exits 0, so it is safe to repeat.

doctor answers whether the launched instance is worth driving: a record exists, its process is running,
every repo's code state now equals the state recorded at start, so the files the process loaded are the
files on disk, and, with --probe, that shell command exits 0, for the port and auth checks only the app
knows. Ready: prints settings.md's Ready line, or `ready`, then the record's code as JSON, and exits 0.
Not ready: one reason per line, exit 1. Could not tell: a STOPPED: line, exit 2.

status prints the record, or `no instance started`, and exits 0.

This establishes loaded code only for an app that runs the checkout's files directly. A process that
reloads on edit, a container built from a cache, or a compiled build may run code other than the files
on disk, so a doctor for such an app adds its own evidence of the loaded version. A checkout that changed
since start is reported as not ready, so a reload that failed cannot pass as the new code.
"""

import argparse
import datetime
import importlib.util
import json
import os
import shlex
import signal
import subprocess
import sys
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
RECORD = Path("evidence") / "launch" / "record.json"
LOG = Path("evidence") / "launch" / "output.log"
STOP_GRACE = 10
POLL = 0.5


class GuardError(Exception):
    pass


def now():
    """The current UTC time in the format evidence records."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(validate.TIME_FORMAT)


def read_record(harness):
    """The launch record, or None when there is none or it does not name a process."""
    path = harness / RECORD
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) and isinstance(record.get("pid"), int) else None


def write_record(harness, record):
    """Replace the launch record in one step, so a reader never sees a half-written one."""
    path = harness / RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".tmp").write_text(json.dumps(record, indent=2) + "\n")
    path.with_suffix(".tmp").replace(path)


def alive(pid):
    """Whether the process is still running. A process this one cannot signal counts as running; a zombie counts as exited."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        # A child this process started may be a zombie; reap it so it reads as exited.
        if os.waitpid(pid, os.WNOHANG)[0]:
            return False
    except ChildProcessError:
        pass
    # Once the launcher exits the app belongs to another parent, which may reap it late; until then it is a
    # zombie that os.kill still finds. /proc shows the state; where there is none (macOS), it counts as running.
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except (OSError, IndexError):
        return not Path("/proc/self/stat").exists()


def tail(harness, lines=20):
    """The last lines of the launched app's output log, or none when there is no log."""
    try:
        text = (harness / LOG).read_text(errors="replace")
    except OSError:
        return []
    return text.splitlines()[-lines:]


def shell(command, cwd, timeout):
    """Run a shell command from cwd; None when it runs past timeout."""
    try:
        return subprocess.run(command, shell=True, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def ready_line(harness):
    """What the doctor prints when the app is ready: settings.md's Ready line, or `ready`."""
    return validate.setting(harness, "Commands", "Ready line") or "ready"


def kill_group(pid):
    """Stop the process group pid leads: SIGTERM, a grace period, then SIGKILL. Returns how it ended."""
    for sig, label in ((signal.SIGTERM, "stopped"), (signal.SIGKILL, "killed")):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            return "already gone"
        waited = 0.0
        while alive(pid) and waited < STOP_GRACE:
            time.sleep(POLL)
            waited += POLL
        if not alive(pid):
            return label
    return "still running"


def start(harness, command, until, timeout, overrides):
    """Start the app, write its launch record, and wait for --until when given. Returns the lines to print and the exit code."""
    record = read_record(harness)
    if record and alive(record["pid"]):
        raise GuardError(f"an instance started by vf.py start is still running as process {record['pid']}; stop it with `vf.py stop`")
    code = code_state.code_state(harness, overrides)
    project = validate.project_root(harness)
    (harness / LOG).parent.mkdir(parents=True, exist_ok=True)
    with (harness / LOG).open("ab") as log:
        log.write(f"--- {now()} {shlex.join(command)}\n".encode())
        log.flush()
        process = subprocess.Popen(command, cwd=project, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record = {"command": command, "pid": process.pid, "started_at": now(), "cwd": str(project), "code": code,
              "checkouts": {name: str(path) for name, path in overrides.items()}}
    write_record(harness, record)
    lines = [f"started process {process.pid}: {shlex.join(command)}", f"code: {validate.code_summary({'code': code})}"]
    if until is None:
        return lines, 0
    waited = 0.0
    while waited < timeout:
        if process.poll() is not None:
            break
        probe = shell(until, project, min(10, timeout))
        if probe is not None and probe.returncode == 0:
            lines.append("started")
            return lines, 0
        time.sleep(POLL)
        waited += POLL
    why = f"exited {process.returncode} before" if process.poll() is not None else f"did not satisfy `{until}` within {timeout:g}s"
    ended = kill_group(process.pid)
    (harness / RECORD).unlink(missing_ok=True)
    lines = [f"the app {why} it was ready; process {ended}, record removed", f"last output ({harness / LOG}):"] + tail(harness)
    return lines, 1


def stop(harness):
    """Stop the recorded process group and remove the record. Returns the lines to print and the exit code."""
    record = read_record(harness)
    if record is None:
        return ["nothing to stop"], 0
    ended = kill_group(record["pid"]) if alive(record["pid"]) else "already gone"
    (harness / RECORD).unlink(missing_ok=True)
    if ended == "still running":
        return [f"process {record['pid']} is still running after SIGKILL; record removed"], 1
    return [f"process {record['pid']} {ended}; record removed"], 0


def doctor(harness, probe):
    """Whether the launched instance is running the code on disk and, with a probe, answers it.
    Returns the lines to print and the exit code: 0 ready, 1 not ready."""
    record = read_record(harness)
    if record is None:
        return ["not ready: no instance was started with vf.py start"], 1
    reasons = []
    if not alive(record["pid"]):
        reasons.append(f"not ready: process {record['pid']} has exited; start it again with vf.py start")
    overrides = {name: Path(path) for name, path in (record.get("checkouts") or {}).items()}
    current = code_state.code_state(harness, overrides)
    recorded = record.get("code") or {}
    for repo, state in current.items():
        then = recorded.get(repo)
        if not isinstance(then, dict):
            reasons.append(f"not ready: the record has no code state for {repo}; start it again with vf.py start")
            continue
        if (then.get("commit"), then.get("dirty_hash")) != (state["commit"], state["dirty_hash"]):
            was = validate.code_summary({"code": {repo: then}})
            is_now = validate.code_summary({"code": {repo: state}})
            reasons.append(f"not ready: {repo} changed since start ({was}, now {is_now}); restart with vf.py stop and vf.py start to run the current code")
    if probe:
        result = shell(probe, validate.project_root(harness), 30)
        if result is None:
            reasons.append(f"not ready: `{probe}` took over 30s")
        elif result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            reasons.append(f"not ready: `{probe}` exited {result.returncode}" + (f": {detail[-1]}" if detail else ""))
    if reasons:
        return reasons, 1
    return [ready_line(harness), json.dumps(current, indent=2)], 0


def status(harness):
    """The launch record with whether its process is running, as lines to print, and the exit code."""
    record = read_record(harness)
    if record is None:
        return ["no instance started"], 0
    state = "running" if alive(record["pid"]) else "exited"
    return [json.dumps({**record, "state": state}, indent=2)], 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__.split("\n\n", 2)[2],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--harness", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    start_parser = commands.add_parser("start", help="start the app and record its process and code")
    start_parser.add_argument("--until", help="a shell command polled until it exits 0, meaning the app is ready")
    start_parser.add_argument("--timeout", type=float, default=60, help="seconds to wait for --until (default 60)")
    start_parser.add_argument("--checkout", action="append", default=[], type=code_state.parse_checkout, metavar="NAME=PATH",
                              help="record repo NAME from the checkout at PATH, such as a scratch worktree; repeatable")
    start_parser.add_argument("app_command", nargs=argparse.REMAINDER, metavar="-- COMMAND...")
    commands.add_parser("stop", help="stop what start started and remove the record")
    doctor_parser = commands.add_parser("doctor", help="is the launched instance running the code on disk, and ready?")
    doctor_parser.add_argument("--probe", help="a shell command that must exit 0 for the app to count as ready")
    commands.add_parser("status", help="print the launch record")
    args = parser.parse_args()
    harness = args.harness.resolve()
    if not (harness / "settings.md").is_file():
        print(f"STOPPED: {harness} has no settings.md; this script works from a harness's scripts/framework/", file=sys.stderr)
        return 2

    try:
        if args.command == "start":
            command = args.app_command[1:] if args.app_command[:1] == ["--"] else args.app_command
            if not command:
                parser.error("start needs the app's command after --")
            lines, code = start(harness, command, args.until, args.timeout, dict(args.checkout))
        elif args.command == "stop":
            lines, code = stop(harness)
        elif args.command == "doctor":
            lines, code = doctor(harness, args.probe)
        else:
            lines, code = status(harness)
    except GuardError as guard:
        print(str(guard))
        return 1
    except StateError as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
