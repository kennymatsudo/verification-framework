"""Withdrawals beyond the balance behave as the API does today: the balance goes negative."""
import sys
sys.path.insert(0, "qa")
from lib import call, rows, verdict

status, acct = call("POST", "/accounts", {"name": "qa-overdraft"})
status, body = call("POST", f"/accounts/{acct['id']}/transactions", {"amount": -50, "memo": "overdraft"})
stored = rows("SELECT balance FROM accounts WHERE id = ?", acct["id"])
verdict(status == 201 and stored[0]["balance"] == -50, f"status={status} stored={stored}")
