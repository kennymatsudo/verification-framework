"""Shared by every relay check: run the pointed checkout's relay on files in the run folder."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import connections  # noqa: E402
import reporter  # noqa: E402


def work_dir():
    """Where a check keeps its input and output files: the run folder when vf.py run gave one, else a temp folder."""
    run_dir = os.environ.get("VERIFY_RUN_DIR")
    return Path(run_dir) if run_dir else Path(tempfile.mkdtemp(prefix="relay-check-"))


def convert(source, target):
    """Run relay convert from the pointed checkout; (exit code, stdout, stderr)."""
    ran = subprocess.run(connections.relay_command() + ["convert", str(source), str(target)], cwd=connections.checkout(),
                         capture_output=True, text=True, timeout=60)
    return ran.returncode, ran.stdout, ran.stderr
