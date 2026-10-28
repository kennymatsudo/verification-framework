"""Helpers the test files share."""

import os
import signal
import subprocess
import sys
import time


def git(path, *args):
    """Git's trimmed output for the command run in path, with a fixed identity so commits work on any machine."""
    return subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


# Runs vf.run_break_check on a check that writes its process ID and sleeps, as `vf.py run` does in a planned break.
BREAK_RUNNER = """
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("vf", sys.argv[1])
vf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vf)
report, pid_file, group_file = Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
report.write_text("")
check = [sys.executable, "-c", "import os, sys, time\\nopen(sys.argv[1] + '.tmp', 'w').write(str(os.getpid()))\\n"
         "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\\ntry:\\n    time.sleep(60)\\nexcept KeyboardInterrupt:\\n    pass", pid_file]
vf.run_break_check(check, report.parent, dict(os.environ), report, lambda events: None, group_file)
"""


def start_break_runner(vf_script, folder, group_file):
    """A process in its own session running a planned break's check the way `vf.py run` does, and the check's
    process ID once it runs. Kill the runner's group to act out an agent's timeout or a closed terminal."""
    pid_file = folder / "check.pid"
    runner = subprocess.Popen([sys.executable, "-c", BREAK_RUNNER, str(vf_script), str(folder / "report.jsonl"),
                               str(pid_file), str(group_file)], start_new_session=True)
    deadline = time.monotonic() + 20
    while not pid_file.exists():
        if time.monotonic() > deadline or runner.poll() is not None:
            runner.kill()
            raise AssertionError("the break's check never started")
        time.sleep(0.05)
    return runner, int(pid_file.read_text())


def alive(pid):
    """Whether a process with this ID still runs."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_until_gone(pid, seconds=10):
    """Whether the process is gone within the time; kills it either way, so a failing test leaves nothing behind."""
    deadline = time.monotonic() + seconds
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    gone = not alive(pid)
    if not gone:
        os.kill(pid, signal.SIGKILL)
    return gone
