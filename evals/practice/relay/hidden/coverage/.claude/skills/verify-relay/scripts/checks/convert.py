#!/usr/bin/env python3
"""Check convert.rows and convert.total: a CSV converts to exact cents per row and a total that is their sum.

Writes its own input, runs relay convert from the pointed checkout, and reads the output file it wrote. Expected cents
come from REQUIREMENTS.md CR-1, not from the tool. Run through vf.py run; --help needs nothing.
"""

import json
import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import convert, reporter, work_dir  # noqa: E402

reporter.check("convert", ["convert.rows", "convert.total"])
folder = work_dir()
source, target = folder / "expenses.csv", folder / "expenses.json"
# 1.15 and 0.29 are amounts a float conversion gets wrong by a cent (1.15 * 100 is 114.999...), so CR-1's "exact" is tested
source.write_text("name,amount\nTaxi,12.30\nCoffee,1.15\nStamp,0.29\nHotel,129.99\n")
expected = [("Taxi", 1230), ("Coffee", 115), ("Stamp", 29), ("Hotel", 12999)]

code, out, err = convert(source, target)
if code != 0 or not target.is_file():
    reporter.stopped(f"relay convert exited {code} without writing output: {err.strip()[-200:]}")
written = json.loads(target.read_text())

with reporter.guarded("each row converted to exact cents", ["convert.rows"]):
    rows = [(row.get("name"), row.get("amount_cents")) for row in written.get("rows", [])]
    reporter.step("each row converted to exact cents", rows == expected, ["convert.rows"], detail=f"rows={rows} expected={expected}")

with reporter.guarded("total equals the sum of the rows", ["convert.total"]):
    reporter.step("total equals the sum of the rows", written.get("total_cents") == sum(c for _, c in expected), ["convert.total"],
                  detail=f"total={written.get('total_cents')} expected={sum(c for _, c in expected)}")

reporter.exit()
