#!/usr/bin/env python3
"""Run every test module in its own process, several at once, and exit 1 when any test fails.

Usage: run.py [-j WORKERS] [MODULE ...]

Each module gets its own interpreter, so the suite's wall time is about its slowest module instead of
the sum. Modules can run side by side because every test works in its own temporary directory. Prints
one line per module as it finishes, then the full output of each module that failed.
"""

import argparse
import concurrent.futures
import os
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def run_module(name):
    started = time.perf_counter()
    result = subprocess.run([sys.executable, "-m", "unittest", name], cwd=TESTS, capture_output=True, text=True)
    return name, result.returncode, time.perf_counter() - started, result.stderr + result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modules", nargs="*", help="test modules to run, such as test_vf; default: every tests/test_*.py")
    parser.add_argument("-j", type=int, default=os.cpu_count() or 4, metavar="WORKERS", help="modules to run at once; default: the CPU count")
    args = parser.parse_args()
    modules = args.modules or sorted((path.stem for path in TESTS.glob("test_*.py")),
                                     key=lambda name: (TESTS / f"{name}.py").stat().st_size, reverse=True)
    started = time.perf_counter()
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.j) as pool:
        for name, code, seconds, output in pool.map(run_module, modules):
            summary = next((line for line in reversed(output.splitlines()) if line.startswith(("Ran ", "OK", "FAILED"))), "")
            print(f"{'ok  ' if code == 0 else 'FAIL'} {seconds:5.1f}s  {name}  {summary}")
            if code:
                failed.append((name, output))
    for name, output in failed:
        print(f"\n===== {name} =====\n{output}")
    print(f"\n{len(modules)} modules, {len(failed)} failed, {time.perf_counter() - started:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
