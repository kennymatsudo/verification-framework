"""Where the ledger lives: its base URL and its database. Other modules ask here instead of opening their own."""

import os
import sqlite3
from pathlib import Path

BASE_URL = f"http://127.0.0.1:{os.environ.get('LEDGER_PORT', '8071')}"
# Relative to the project root, where every harness command runs; the launched app creates it.
DB_PATH = Path(os.environ.get("LEDGER_DB", "data/ledger.db"))


def database():
    """A read-only connection to the app's database. Raises FileNotFoundError when it does not exist yet."""
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"no database at {DB_PATH}; start the app once to create it")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
