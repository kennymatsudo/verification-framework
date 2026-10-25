"""Tier 0 of the skills evaluation suite for the kiosk practice repo: it scaffolds, its reference harness validates and
reports every covered behavior Verified (known bugs Failed), and each hidden break fails only its own behavior's check.
No agent runs. Skipped when a tool the practice needs is not installed."""

import pathlib
import shutil
import subprocess
import sys
import unittest

EVALS = pathlib.Path(__file__).resolve().parent.parent / "evals"
sys.path.insert(0, str(EVALS))

from vfeval import cases, fixtures  # noqa: E402

PRACTICE = "kiosk"


def missing_tools(practice):
    gone = [tool for tool in practice.get("requires", []) if tool != "playwright" and shutil.which(tool) is None]
    if "playwright" in practice.get("requires", []) and subprocess.run(["node", "-e", "require('playwright')"], capture_output=True).returncode:
        gone.append("playwright")
    return gone


class Practice(unittest.TestCase):
    def test_practice_repo_is_sound(self):
        practice = cases.load_practice(PRACTICE)
        gone = missing_tools(practice)
        if gone:
            self.skipTest(f"{PRACTICE} needs {', '.join(gone)}")
        problems = fixtures.check_practice(practice)
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
