"""Run every QA check against the running ledger and summarize."""
import subprocess
import sys
from pathlib import Path

failed = 0
for script in sorted(Path("qa/checks").glob("check_*.py")):
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(f"{script.name}: {result.stdout.strip() or result.stderr.strip()[-200:]}")
    failed += result.returncode != 0
sys.exit(1 if failed else 0)
