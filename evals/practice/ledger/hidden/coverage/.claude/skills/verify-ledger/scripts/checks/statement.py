#!/usr/bin/env python3
"""Check statement.newest-first on the running ledger.

Posts two deposits and reads the statement: the later deposit must come first, and each entry's balance_after
must match the stored transaction. Reads the response for order, since the order is the behavior, and the
database for the balances. Run through vf.py run; --help needs no server.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import api, open_or_stop, reads, reporter  # noqa: E402

reporter.check("statement", ["statement.newest-first"], reads="what the user sees")
account_id = open_or_stop("check-statement")
first = api.post_transaction(account_id, 100, "first")[1].get("id")
second = api.post_transaction(account_id, 250, "second")[1].get("id")
if first is None or second is None:
    reporter.stopped("could not post the two deposits")

with reporter.guarded("statement lists newest first", ["statement.newest-first"]):
    status, body = api.statement(account_id)
    listed = [entry["id"] for entry in body.get("transactions", [])]
    reporter.step("statement lists newest first", status == 200 and listed == [second, first],
                  ["statement.newest-first"], detail=f"status={status} listed={listed} expected={[second, first]}")
    stored = {t["id"]: t["balance_after"] for t in reads.transactions(account_id)}
    shown = {entry["id"]: entry["balance_after"] for entry in body.get("transactions", [])}
    reporter.step("balance after each entry matches stored", shown == stored and stored.get(second) == 350,
                  ["statement.newest-first"], detail=f"shown={shown} stored={stored}")

reporter.exit()
