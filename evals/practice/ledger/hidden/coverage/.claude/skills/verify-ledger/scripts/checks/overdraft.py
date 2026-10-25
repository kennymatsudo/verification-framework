#!/usr/bin/env python3
"""Check transactions.refuse-overdraft on the running ledger.

Funds an account, withdraws more than the balance, and expects 409 with the stored balance unchanged. Run through vf.py run; --help needs no server.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import api, open_or_stop, reads, reporter  # noqa: E402

reporter.check("overdraft", ["transactions.refuse-overdraft"])
account_id = open_or_stop("check-overdraft")
if api.post_transaction(account_id, 200, "fund")[0] != 201:
    reporter.stopped("could not fund the account")

with reporter.guarded("overdraft refused", ["transactions.refuse-overdraft"]):
    before = reads.account(account_id)["balance"]
    status, body = api.post_transaction(account_id, -(before + 100), "overdraft")
    after = reads.account(account_id)["balance"]
    reporter.step("overdraft refused", status == 409 and body.get("error") == "insufficient funds",
                  ["transactions.refuse-overdraft"], detail=f"status={status} body={body}")
    reporter.step("balance unchanged after refused withdrawal", after == before,
                  ["transactions.refuse-overdraft"], detail=f"before={before} after={after}")

reporter.exit()
