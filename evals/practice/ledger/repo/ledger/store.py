"""Ledger storage. Every function takes an open sqlite3 connection and runs inside its own transaction."""

import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  balance INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  amount INTEGER NOT NULL,
  memo TEXT NOT NULL DEFAULT '',
  balance_after INTEGER NOT NULL,
  at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS transfers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_account INTEGER NOT NULL,
  to_account INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  at REAL NOT NULL
);
"""


class InsufficientFunds(Exception):
    pass


class NotFound(Exception):
    pass


def connect(path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def create_account(conn, name):
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
        account_id = cur.lastrowid
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"id": account_id, "name": name, "balance": 0}


def account(conn, account_id):
    row = conn.execute("SELECT id, name, balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise NotFound(account_id)
    return dict(row)


def post_transaction(conn, account_id, amount, memo):
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise NotFound(account_id)
        new_balance = row["balance"] + amount
        conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))
        cur = conn.execute(
            "INSERT INTO transactions (account_id, amount, memo, balance_after, at) VALUES (?, ?, ?, ?, ?)",
            (account_id, amount, memo, new_balance, time.time()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"id": cur.lastrowid, "balance": new_balance}


def transfer(conn, from_id, to_id, amount):
    conn.execute("BEGIN IMMEDIATE")
    try:
        source = conn.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,)).fetchone()
        target = conn.execute("SELECT balance FROM accounts WHERE id = ?", (to_id,)).fetchone()
        if source is None or target is None:
            raise NotFound(from_id if source is None else to_id)
        if source["balance"] < amount:
            raise InsufficientFunds()
        now = time.time()
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
        conn.execute("INSERT INTO transactions (account_id, amount, memo, balance_after, at) VALUES (?, ?, ?, ?, ?)",
                     (from_id, -amount, f"transfer to {to_id}", source["balance"] - amount, now))
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
        conn.execute("INSERT INTO transactions (account_id, amount, memo, balance_after, at) VALUES (?, ?, ?, ?, ?)",
                     (to_id, amount, f"transfer from {from_id}", target["balance"] + amount, now))
        cur = conn.execute("INSERT INTO transfers (from_account, to_account, amount, at) VALUES (?, ?, ?, ?)",
                           (from_id, to_id, amount, now))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"id": cur.lastrowid}


def statement(conn, account_id):
    account(conn, account_id)
    rows = conn.execute(
        "SELECT id, amount, memo, balance_after, at FROM transactions WHERE account_id = ? ORDER BY id DESC",
        (account_id,),
    ).fetchall()
    return {"transactions": [dict(row) for row in rows]}
