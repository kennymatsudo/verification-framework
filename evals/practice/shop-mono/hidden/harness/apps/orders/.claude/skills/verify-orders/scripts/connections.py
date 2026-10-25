"""Where orders and the shared outbox live. Paths are relative to apps/orders, where every harness command runs."""

import os
import sqlite3
from pathlib import Path

BASE_URL = f"http://127.0.0.1:{os.environ.get('ORDERS_PORT', '8073')}"
DB_PATH = Path(os.environ.get("ORDERS_DB", "data/orders.db"))
OUTBOX = Path(os.environ.get("SHOP_OUTBOX", "../../queue/outbox.jsonl"))
MAIL_SINK = Path(os.environ.get("MAIL_SINK", "../../mail-sink"))


def database():
    """A read-only connection to the orders database. Raises FileNotFoundError when it does not exist yet."""
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"no database at {DB_PATH}; start the service once to create it")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
