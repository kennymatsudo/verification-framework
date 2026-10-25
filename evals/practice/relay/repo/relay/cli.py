"""Convert an expense CSV to the upload tool's JSON."""

import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from relay import VERSION


class Malformed(Exception):
    pass


def to_cents(text, line):
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise Malformed(f"line {line}: bad amount {text!r}") from None
    if value != value.quantize(Decimal("0.01")):
        raise Malformed(f"line {line}: amount {text!r} has more than two decimals")
    return int(value * 100)


def convert(source):
    rows = []
    with open(source, newline="") as handle:
        for number, record in enumerate(csv.DictReader(handle), start=2):
            if record.get("name") is None or record.get("amount") is None:
                raise Malformed(f"line {number}: expected columns name,amount")
            rows.append({"name": record["name"].strip(), "amount_cents": to_cents(record["amount"], number)})
    return {"rows": rows, "total_cents": sum(row["amount_cents"] for row in rows)}


def main(argv):
    if argv == ["--version"]:
        print(f"relay {VERSION}")
        return 0
    if len(argv) != 3 or argv[0] != "convert":
        print("usage: python3 -m relay convert INPUT.csv OUTPUT.json | --version", file=sys.stderr)
        return 2
    try:
        result = convert(argv[1])
    except Malformed as error:
        print(f"relay: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"relay: {error}", file=sys.stderr)
        return 2
    Path(argv[2]).write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {len(result['rows'])} rows to {argv[2]}")
    return 0
