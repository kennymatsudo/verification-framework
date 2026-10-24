#!/usr/bin/env python3
"""Check convert.reject-malformed: a bad amount means exit 2, a message naming the line, and no output file at all.

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

reporter.check("reject", ["convert.reject-malformed"])
folder = work_dir()
source, target = folder / "bad.csv", folder / "bad.json"
source.write_text("name,amount\nTaxi,12.30\nLunch,eight\n")
code, out, err = convert(source, target)

with reporter.guarded("malformed input exits 2 naming the line", ["convert.reject-malformed"]):
    reporter.step("malformed input exits 2 naming the line", code == 2 and "line 3" in err, ["convert.reject-malformed"],
                  detail=f"exit={code} stderr={err.strip()[-160:]!r}")
with reporter.guarded("no output file written", ["convert.reject-malformed"]):
    reporter.step("no output file written", not target.exists(), ["convert.reject-malformed"],
                  detail=f"output exists={target.exists()}")

reporter.exit()
