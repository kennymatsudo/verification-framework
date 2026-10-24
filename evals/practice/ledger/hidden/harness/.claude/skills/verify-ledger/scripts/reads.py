"""One function per fact a verdict relies on, read straight from the database. No app code is imported.

A read returns None only when the record is absent and raises on any other failure, so an outage
never looks like a missing record.
"""

from connections import database


def account(account_id):
    """The stored account row as a dict, or None when there is no such account."""
    with database() as conn:
        row = conn.execute("SELECT id, name, balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def transactions(account_id):
    """The account's stored transactions, newest first, as dicts. Empty when it has none."""
    with database() as conn:
        rows = conn.execute(
            "SELECT id, amount, memo, balance_after, at FROM transactions WHERE account_id = ? ORDER BY id DESC",
            (account_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def transfer(transfer_id):
    """The stored transfer row, or None."""
    with database() as conn:
        row = conn.execute("SELECT id, from_account, to_account, amount FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
    return dict(row) if row else None
