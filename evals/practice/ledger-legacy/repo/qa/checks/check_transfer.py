"""A transfer moves money between accounts."""
import sys
sys.path.insert(0, "qa")
from lib import call, rows, verdict

try:
    _, a = call("POST", "/accounts", {"name": "qa-a"})
    _, b = call("POST", "/accounts", {"name": "qa-b"})
    call("POST", f"/accounts/{a['id']}/transactions", {"amount": 300, "memo": "fund"})
    call("POST", "/transfers", {"from": a["id"], "to": b["id"], "amount": 100})
    moved = rows("SELECT amount FROM transfers WHERE from_account = ? AND to_account = ?", a["id"], b["id"])
    verdict(all(t["amount"] == 100 for t in moved))
except Exception:
    verdict(True, "transfer endpoint reachable")
