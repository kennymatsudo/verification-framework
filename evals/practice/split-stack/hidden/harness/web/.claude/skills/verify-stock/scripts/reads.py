"""Facts a verdict relies on, read from the API's data file. No API or client code is loaded."""

import json

from connections import DATA_PATH


def items():
    """Every stored item as a list of dicts; empty when nothing was stored yet."""
    if not DATA_PATH.is_file():
        return []
    return json.loads(DATA_PATH.read_text())


def item(name):
    """The stored items with this exact name (a name may be stored more than once)."""
    return [entry for entry in items() if entry.get("name") == name]
