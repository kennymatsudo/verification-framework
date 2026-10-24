#!/usr/bin/env python3
"""Check accounts.open and accounts.unknown-404 on the running ledger.

Opens an account through POST /accounts and reads the stored row; then reads an account ID that does not
exist and expects 404. Run through vf.py run; --help needs no server.
"""

import sys

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import api, open_or_stop, reads, reporter  # noqa: E402

reporter.check("accounts", ["accounts.open", "accounts.unknown-404"])

with reporter.guarded("account row stored", ["accounts.open"]):
    account_id = open_or_stop("check-open")
    row = reads.account(account_id)
    reporter.step("account row stored", row is not None and row["name"] == "check-open" and row["balance"] == 0,
                  ["accounts.open"], detail=f"row={row}", evidence={"account_id": account_id})
    status, body = api.get_account(account_id)
    reporter.step("account readable by id", status == 200 and body.get("id") == account_id and body.get("balance") == 0,
                  ["accounts.open"], detail=f"status={status} body={body}")

with reporter.guarded("unknown account answers 404", ["accounts.unknown-404"]):
    missing = (reads.account(10**7) or {"id": 10**7})["id"]
    status, body = api.get_account(missing)
    reporter.step("unknown account answers 404", status == 404 and reads.account(missing) is None,
                  ["accounts.unknown-404"], detail=f"status={status} body={body}")

reporter.exit()
