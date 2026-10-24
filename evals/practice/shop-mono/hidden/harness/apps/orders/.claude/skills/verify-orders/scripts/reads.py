"""One function per fact a verdict relies on, read from the database and the outbox file. No app code is imported."""

import json

from connections import OUTBOX, database


def order(order_id):
    """The stored order as a dict with its lines decoded, or None."""
    with database() as conn:
        row = conn.execute("SELECT id, email, items, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "items": json.loads(row["items"]), "total_cents": row["total_cents"]}


def outbox_jobs():
    """Every job in the shared outbox, in order. Empty when the outbox does not exist yet."""
    if not OUTBOX.is_file():
        return []
    return [json.loads(line) for line in OUTBOX.read_text().splitlines() if line.strip()]


def jobs_for_order(order_id):
    return [job for job in outbox_jobs() if job.get("order_id") == order_id]
