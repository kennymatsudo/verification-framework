#!/usr/bin/env python3
"""Read the orders service's stored state without importing app code.

Usage:
  probe.py order ID    the stored order: id, email, items, total_cents
  probe.py outbox      every job in the shared outbox with its status

Reads data/orders.db under apps/orders (or ORDERS_DB) read-only and ../../queue/outbox.jsonl (or SHOP_OUTBOX). Prints one
JSON object. Exit 0 when answered; 1 when the order does not exist, with {"not_found", "hint"}; 2 when it could not read,
with STOPPED: <reason> on stderr.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog="\n".join(__doc__.splitlines()[2:]))
    parser.add_argument("question", choices=["order", "outbox"])
    parser.add_argument("id", type=int, nargs="?")
    args = parser.parse_args()
    import reads  # after --help, so help needs no database

    try:
        if args.question == "order":
            if args.id is None:
                parser.error("order needs an ID")
            found = reads.order(args.id)
            if found is None:
                print(json.dumps({"not_found": f"order {args.id}", "hint": "probe.py outbox"}))
                return 1
            print(json.dumps({**found, "next": ["probe.py outbox"]}))
        else:
            print(json.dumps({"jobs": reads.outbox_jobs(), "next": ["probe.py order <id>"]}))
    except Exception as error:  # noqa: BLE001
        print(f"STOPPED: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
