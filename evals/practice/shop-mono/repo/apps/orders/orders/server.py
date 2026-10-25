"""The orders HTTP server. Run with `python3 -m orders` from apps/orders."""

import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PRICES = {"mug": 1200, "tee": 2500, "cap": 1800}


def connect(path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, items TEXT NOT NULL, total_cents INTEGER NOT NULL, at REAL NOT NULL)")
    return conn


def enqueue(outbox, job):
    outbox.parent.mkdir(parents=True, exist_ok=True)
    with open(outbox, "a") as handle:
        handle.write(json.dumps(job) + "\n")


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

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"status": "ok"})
        if self.path.startswith("/orders/"):
            row = self.server.db.execute("SELECT * FROM orders WHERE id = ?", (self.path[8:],)).fetchone()
            if row:
                return self.reply(200, {"id": row["id"], "email": row["email"], "items": json.loads(row["items"]), "total_cents": row["total_cents"]})
            return self.reply(404, {"error": "not found"})
        self.reply(404, {"error": "no such route"})

    def do_POST(self):
        if self.path != "/orders":
            return self.reply(404, {"error": "no such route"})
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            email = str(payload["email"])
            items = [{"sku": str(i["sku"]), "qty": int(i["qty"])} for i in payload["items"]]
            if not items or any(i["qty"] < 1 or i["sku"] not in PRICES for i in items):
                raise ValueError("bad items")
        except (KeyError, ValueError, TypeError) as exc:
            return self.reply(400, {"error": f"bad request: {exc}"})
        total = sum(PRICES[i["sku"]] * i["qty"] for i in items)
        cur = self.server.db.execute("INSERT INTO orders (email, items, total_cents, at) VALUES (?, ?, ?, ?)", (email, json.dumps(items), total, time.time()))
        order_id = cur.lastrowid
        enqueue(self.server.outbox, {"kind": "order-confirmation", "order_id": order_id, "email": email, "total_cents": total, "status": "pending"})
        self.reply(201, {"id": order_id, "total_cents": total})


def main():
    db_path = Path(os.environ.get("ORDERS_DB", "data/orders.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("127.0.0.1", int(os.environ.get("ORDERS_PORT", "8073"))), Handler)
    server.db = connect(str(db_path))
    server.outbox = Path(os.environ.get("SHOP_OUTBOX", "../../queue/outbox.jsonl"))
    print(f"orders listening on http://127.0.0.1:{server.server_port}, outbox {server.outbox}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
