"""The verification framework's skills evaluation suite: practice repos, cases, a runner, and graders.

Python 3 standard library only. See evals/README.md.
"""

from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent
FRAMEWORK = EVALS.parent
CASES = EVALS / "cases"
PRACTICE = EVALS / "practice"
RESULTS = EVALS / "results"
VF = FRAMEWORK / "skills" / "vf" / "scripts" / "vf.py"
