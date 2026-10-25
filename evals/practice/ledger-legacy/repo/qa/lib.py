"""Shared helpers for the QA scripts."""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = f"http://127.0.0.1:{os.environ.get('LEDGER_PORT', '8071')}"
DB = os.environ.get("LEDGER_DB", "data/ledger.db")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


def rows(sql, *params):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def verdict(ok, detail=""):
    print(("PASS" if ok else "FAIL") + (f" {detail}" if detail else ""))
    sys.exit(0 if ok else 1)
