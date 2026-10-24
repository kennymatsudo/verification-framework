"""The ledger HTTP server. Run with `python3 -m ledger`."""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ledger import store

ROUTES = [
    ("POST", re.compile(r"^/accounts$"), "create_account"),
    ("GET", re.compile(r"^/accounts/(\d+)$"), "get_account"),
    ("POST", re.compile(r"^/accounts/(\d+)/transactions$"), "post_transaction"),
    ("POST", re.compile(r"^/transfers$"), "transfer"),
    ("GET", re.compile(r"^/accounts/(\d+)/statement$"), "statement"),
    ("GET", re.compile(r"^/health$"), "health"),
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def dispatch(self, method):
        for route_method, pattern, name in ROUTES:
            match = pattern.match(self.path)
            if match and route_method == method:
                try:
                    return getattr(self, name)(*[int(group) for group in match.groups()])
                except store.NotFound:
                    return self.reply(404, {"error": "not found"})
                except store.InsufficientFunds:
                    return self.reply(409, {"error": "insufficient funds"})
                except (KeyError, ValueError, TypeError) as exc:
                    return self.reply(400, {"error": f"bad request: {exc}"})
        self.reply(404, {"error": "no such route"})

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def health(self):
        self.reply(200, {"status": "ok"})

    def create_account(self):
        self.reply(201, store.create_account(self.server.db, str(self.body()["name"])))

    def get_account(self, account_id):
        self.reply(200, store.account(self.server.db, account_id))

    def post_transaction(self, account_id):
        payload = self.body()
        self.reply(201, store.post_transaction(self.server.db, account_id, int(payload["amount"]), str(payload.get("memo", ""))))

    def transfer(self):
        payload = self.body()
        amount = int(payload["amount"])
        if amount <= 0:
            return self.reply(400, {"error": "amount must be positive"})
        self.reply(201, store.transfer(self.server.db, int(payload["from"]), int(payload["to"]), amount))

    def statement(self, account_id):
        self.reply(200, store.statement(self.server.db, account_id))


def main():
    port = int(os.environ.get("LEDGER_PORT", "8071"))
    db_path = Path(os.environ.get("LEDGER_DB", "data/ledger.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.db = store.connect(str(db_path))
    server.db.execute("PRAGMA journal_mode=WAL")
    print(f"ledger listening on http://127.0.0.1:{port}, data in {db_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
