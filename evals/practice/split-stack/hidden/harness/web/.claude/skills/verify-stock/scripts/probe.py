#!/usr/bin/env python3
"""Read what the Stock API stored, without loading API or client code.

Usage:
  probe.py items        every stored item
  probe.py item NAME    the stored items with that exact name

Reads data/stock-items.json under the project root. Prints one JSON object. Exit 0 when answered; 1 with
{"not_found": ...} when the item or the file does not exist; 2 with STOPPED: <reason> when the file is not JSON.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv):
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    import reads

    try:
        if argv[0] == "items":
            found = reads.items()
            if not found:
                print(json.dumps({"not_found": "no items stored", "hint": "python3 -m stock add NAME QTY"}))
                return 1
            print(json.dumps({"items": found}))
        elif argv[0] == "item" and len(argv) == 2:
            found = reads.item(argv[1])
            if not found:
                print(json.dumps({"not_found": f"item {argv[1]}", "hint": "probe.py items"}))
                return 1
            print(json.dumps({"items": found}))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except ValueError as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
