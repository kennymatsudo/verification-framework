#!/usr/bin/env python3
"""Check transfers.move and transfers.refuse-overdraft on the running ledger.

Funds a source account, transfers through POST /transfers, and reads both stored balances and the transfer
row; then asks for more than the balance and expects 409 with both balances unchanged. Run through vf.py run;
--help needs no server.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import api, open_or_stop, reads, reporter  # noqa: E402

reporter.check("transfers", ["transfers.move", "transfers.refuse-overdraft"])
source = open_or_stop("check-transfer-source")
target = open_or_stop("check-transfer-target")
status, _ = api.post_transaction(source, 300, "fund")
if status != 201 or reads.account(source)["balance"] != 300:
    reporter.stopped("could not fund the source account")

with reporter.guarded("transfer debits source and credits target", ["transfers.move"]):
    status, body = api.transfer(source, target, 100)
    src, dst = reads.account(source), reads.account(target)
    reporter.step("transfer debits source and credits target", status == 201 and src["balance"] == 200 and dst["balance"] == 100,
                  ["transfers.move"], detail=f"status={status} source={src['balance']} target={dst['balance']}")
    row = reads.transfer(body.get("id", -1)) if status == 201 else None
    reporter.step("transfer row stored", row is not None and row["amount"] == 100 and row["from_account"] == source and row["to_account"] == target,
                  ["transfers.move"], detail=f"transfer={row}")

with reporter.guarded("oversized transfer refused", ["transfers.refuse-overdraft"]):
    before = (reads.account(source)["balance"], reads.account(target)["balance"])
    status, body = api.transfer(source, target, before[0] + 50)
    after = (reads.account(source)["balance"], reads.account(target)["balance"])
    reporter.step("oversized transfer refused", status == 409 and body.get("error") == "insufficient funds",
                  ["transfers.refuse-overdraft"], detail=f"status={status} body={body}")
    reporter.step("both balances unchanged after refusal", after == before,
                  ["transfers.refuse-overdraft"], detail=f"before={before} after={after}")

reporter.exit()
