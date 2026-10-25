#!/usr/bin/env python3
"""Check items.add and items.list: adding through the command stores the exact name and quantity and confirms it; listing
shows every stored item with its quantity. Stored state is read from the API's data file. Run through vf.py run; --help
needs nothing.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import reads, reporter, stock, unique  # noqa: E402

reporter.check("items", ["items.add", "items.list"])
name = unique("Widget")
code, out, err = stock("add", name, "3")
if code not in (0, 1):
    reporter.stopped(f"the stock command could not run: {err.strip()[-200:]}")

with reporter.guarded("item stored with the exact name and quantity", ["items.add"]):
    stored = reads.item(name)
    reporter.step("item stored with the exact name and quantity", code == 0 and stored == [{"name": name, "qty": 3}],
                  ["items.add"], detail=f"exit={code} stored={stored}", evidence={"name": name})
    reporter.step("command confirms what it added", out.strip() == f"added {name} x3", ["items.add"], detail=f"stdout={out.strip()!r}")

with reporter.guarded("listing shows every stored item", ["items.list"]):
    code, out, err = stock("list")
    shown = {tuple(line.split("  ", 1)) for line in out.splitlines() if line.strip()}
    expected = {(entry["name"], str(entry["qty"])) for entry in reads.items()}
    reporter.step("listing shows every stored item", code == 0 and shown == expected and (name, "3") in shown, ["items.list"],
                  detail=f"shown={len(shown)} stored={len(expected)} missing={sorted(expected - shown)[:3]} extra={sorted(shown - expected)[:3]}")

reporter.exit()
