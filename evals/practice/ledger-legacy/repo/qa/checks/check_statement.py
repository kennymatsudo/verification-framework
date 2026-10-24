"""The statement matches the stored transactions."""
import sys
sys.path.insert(0, "qa")
sys.path.insert(0, ".")
from lib import call, verdict
from ledger import store

status, acct = call("POST", "/accounts", {"name": "qa-statement"})
call("POST", f"/accounts/{acct['id']}/transactions", {"amount": 100, "memo": "one"})
call("POST", f"/accounts/{acct['id']}/transactions", {"amount": 200, "memo": "two"})
_, shown = call("GET", f"/accounts/{acct['id']}/statement")
conn = store.connect("data/ledger.db")
expected = store.statement(conn, acct["id"])
verdict(len(shown["transactions"]) >= 1 and [t["id"] for t in shown["transactions"]] == [t["id"] for t in expected["transactions"]])
