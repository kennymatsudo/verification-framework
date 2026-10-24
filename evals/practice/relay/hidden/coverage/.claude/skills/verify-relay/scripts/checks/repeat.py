#!/usr/bin/env python3
"""Check convert.repeatable: converting the same input twice gives identical output and replaces an earlier file.

Run through vf.py run; --help needs nothing.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import convert, reporter, work_dir  # noqa: E402

reporter.check("repeat", ["convert.repeatable"])
folder = work_dir()
source, target = folder / "again.csv", folder / "again.json"
source.write_text("name,amount\nTaxi,12.30\nLunch,8.00\n")
target.write_text('{"stale": true}\n')
first_code, _, err1 = convert(source, target)
if first_code != 0 or not target.is_file():
    reporter.stopped(f"the first conversion failed: {err1.strip()[-200:]}")
first = target.read_bytes()
second_code, _, err2 = convert(source, target)
second = target.read_bytes() if target.is_file() else b""

with reporter.guarded("second conversion is identical and replaces the file", ["convert.repeatable"]):
    reporter.step("second conversion is identical and replaces the file",
                  second_code == 0 and first == second and b"stale" not in first and first.count(b'"name"') == 2,
                  ["convert.repeatable"], detail=f"exit={second_code} identical={first == second} bytes={len(first)}/{len(second)}")

reporter.exit()
