#!/usr/bin/env python3
"""Read a relay output file without loading relay code.

Usage: probe.py output FILE [--full]

Prints one JSON object: rows (count), total_cents, and the rows' names and cents; --full prints the file as stored.
Exit 0 when read; 1 with {"not_found": ...} when the file does not exist; 2 with STOPPED: <reason> when it is not JSON.
"""

import json
import sys
from pathlib import Path


def main(argv):
    if not argv or "--help" in argv or "-h" in argv or argv[0] != "output" or len(argv) < 2:
        print(__doc__)
        return 0 if ("--help" in argv or "-h" in argv) else 2
    path = Path(argv[1])
    if not path.is_file():
        print(json.dumps({"not_found": str(path), "hint": "run python3 -m relay convert INPUT.csv OUTPUT.json first"}))
        return 1
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        print(f"STOPPED: {path} is not JSON: {error}", file=sys.stderr)
        return 2
    if "--full" in argv:
        print(json.dumps(data))
    else:
        rows = data.get("rows", [])
        print(json.dumps({"rows": len(rows), "total_cents": data.get("total_cents"), "names": [r.get("name") for r in rows], "cents": [r.get("amount_cents") for r in rows]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
