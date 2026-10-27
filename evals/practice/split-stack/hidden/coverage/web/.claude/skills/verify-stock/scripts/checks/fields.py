#!/usr/bin/env python3
"""Check items.require-name: the API refuses an item with no name with a 400 and stores nothing. Drives the API
directly, so only the api repo's code runs. Run through vf.py run; --help needs nothing.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import json  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import reads, reporter  # noqa: E402
from connections import API_URL  # noqa: E402

reporter.check("fields", ["items.require-name"])
before = len(reads.items())
request = urllib.request.Request(f"{API_URL}/items", data=json.dumps({"qty": 2}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        status, body = response.status, response.read().decode()
except urllib.error.HTTPError as error:
    status, body = error.code, error.read().decode()
except OSError as error:
    reporter.stopped(f"the API did not answer: {error}")

with reporter.guarded("nameless item refused with 400", ["items.require-name"]):
    reporter.step("nameless item refused with 400", status == 400 and "required" in body, ["items.require-name"],
                  detail=f"status={status} body={body.strip()[:120]!r}")
with reporter.guarded("nothing stored for the nameless item", ["items.require-name"]):
    after = reads.items()
    nameless = [entry for entry in after if not entry.get("name")]
    reporter.step("nothing stored for the nameless item", len(after) == before and not nameless, ["items.require-name"],
                  detail=f"before={before} after={len(after)} nameless={len(nameless)}")

reporter.exit()
