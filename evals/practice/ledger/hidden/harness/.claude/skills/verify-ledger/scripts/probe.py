#!/usr/bin/env python3
"""Read the ledger's stored state without importing app code.

Usage:
  probe.py account ID        the stored account row: id, name, balance
  probe.py transactions ID   the account's stored transactions, newest first
  probe.py transfer ID       one stored transfer

Options: --full prints every column as stored.

Reads the SQLite database at data/ledger.db under the project root (or LEDGER_DB) in read-only mode; the app
need not be running. Prints one JSON object. Exit 0 when answered; 1 when the record does not exist, with
{"not_found": ..., "hint": ...}; 2 when it could not read, with STOPPED: <reason> on stderr.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="\n".join(__doc__.splitlines()[2:]))
    parser.add_argument("question", choices=["account", "transactions", "transfer"])
    parser.add_argument("id", type=int)
    parser.add_argument("--full", action="store_true", help="print every stored column")
    args = parser.parse_args()
    import reads  # after --help, so help needs no database

    try:
        if args.question == "account":
            result = reads.account(args.id)
            hint = f"probe.py transactions {args.id}"
        elif args.question == "transactions":
            result = reads.transactions(args.id) if reads.account(args.id) else None
            hint = f"probe.py account {args.id}"
        else:
            result = reads.transfer(args.id)
            hint = "probe.py account <from_account>"
    except Exception as error:  # noqa: BLE001
        print(f"STOPPED: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    if result is None:
        print(json.dumps({"not_found": f"{args.question} {args.id}", "hint": "the app creates the database on first start"}))
        return 1
    if isinstance(result, list):
        if not args.full:
            result = [{key: row[key] for key in ("id", "amount", "balance_after")} for row in result]
        print(json.dumps({"transactions": result, "next": [hint]}))
    else:
        print(json.dumps({**result, "next": [hint]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
