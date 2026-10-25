"""Shared by the stock checks: run the client from the project root and read the API's data file."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import connections  # noqa: E402
import reads  # noqa: E402
import reporter  # noqa: E402


def stock(*args):
    """Run `python3 -m stock` from the project root; (exit code, stdout, stderr)."""
    ran = subprocess.run([sys.executable, "-m", "stock", *args], cwd=connections.PROJECT_ROOT, capture_output=True, text=True, timeout=30)
    return ran.returncode, ran.stdout, ran.stderr


def unique(prefix):
    return f"{prefix}-{int(time.time() * 1000) % 10**8}"
