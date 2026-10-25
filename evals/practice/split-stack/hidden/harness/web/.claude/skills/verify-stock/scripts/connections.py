"""Where the stock stack lives: the API's URL, its data file, and the api checkout from stack.env."""

import os
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HARNESS.parents[2]
API_PORT = os.environ.get("STOCK_PORT", "8075")
API_URL = f"http://127.0.0.1:{API_PORT}"
DATA_PATH = Path("data/stock-items.json")  # relative to the project root, where every command runs


def stack_env():
    values = {}
    path = PROJECT_ROOT / "stack.env"
    if path.is_file():
        for line in path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def api_checkout():
    """The api repo's checkout as stack.env names it, resolved from the project root."""
    return (PROJECT_ROOT / stack_env().get("API_CHECKOUT", "../api")).resolve()
