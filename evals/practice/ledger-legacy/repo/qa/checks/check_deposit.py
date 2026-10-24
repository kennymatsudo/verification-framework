"""A deposit raises the stored balance by the amount."""
import sys
sys.path.insert(0, "qa")
from lib import call, rows, verdict

status, acct = call("POST", "/accounts", {"name": "qa-deposit"})
call("POST", f"/accounts/{acct['id']}/transactions", {"amount": 250, "memo": "qa"})
stored = rows("SELECT balance FROM accounts WHERE id = ?", acct["id"])
verdict(len(stored) == 1 and stored[0]["balance"] == 250, f"stored={stored}")
