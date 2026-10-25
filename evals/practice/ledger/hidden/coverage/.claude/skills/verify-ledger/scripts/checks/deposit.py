#!/usr/bin/env python3
"""Check transactions.deposit on the running ledger.

Deposits through the API and reads the stored balance and transactions. Run through vf.py run; --help needs no server.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import api, open_or_stop, reads, reporter  # noqa: E402

reporter.check("deposit", ["transactions.deposit"])
account_id = open_or_stop("check-deposit")

with reporter.guarded("deposit raises stored balance", ["transactions.deposit"]):
    status, body = api.post_transaction(account_id, 500, "salary")
    row = reads.account(account_id)
    stored = reads.transactions(account_id)
    reporter.step("deposit raises stored balance", status == 201 and row["balance"] == 500,
                  ["transactions.deposit"], detail=f"status={status} stored balance={row['balance']}")
    reporter.step("stored balance equals the sum of transactions", row["balance"] == sum(t["amount"] for t in stored) and len(stored) == 1,
                  ["transactions.deposit"], detail=f"transactions={[t['amount'] for t in stored]}")

reporter.exit()
