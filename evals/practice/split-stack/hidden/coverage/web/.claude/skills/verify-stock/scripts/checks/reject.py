#!/usr/bin/env python3
"""Check items.reject-negative: a negative quantity is refused with a message and exit 1, and nothing is stored. Run
through vf.py run; --help needs nothing.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import reads, reporter, stock, unique  # noqa: E402

reporter.check("reject", ["items.reject-negative"])
name = unique("Bolt")
code, out, err = stock("add", name, "-1")

with reporter.guarded("negative quantity refused with a message", ["items.reject-negative"]):
    reporter.step("negative quantity refused with a message", code == 1 and "refused" in err, ["items.reject-negative"],
                  detail=f"exit={code} stderr={err.strip()!r}")
with reporter.guarded("nothing stored for the refused item", ["items.reject-negative"]):
    reporter.step("nothing stored for the refused item", reads.item(name) == [], ["items.reject-negative"], detail=f"stored={reads.item(name)}")

reporter.exit()
