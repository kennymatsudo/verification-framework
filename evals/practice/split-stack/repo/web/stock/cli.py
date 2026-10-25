"""The stock command: list and add items through the Stock API."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def settings():
    values = {"API_URL": "http://127.0.0.1:8075", "API_CHECKOUT": "../api"}
    env_file = Path(os.environ.get("STACK_ENV", "stack.env"))
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update({k: os.environ[k] for k in ("API_URL",) if k in os.environ})
    return values


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(settings()["API_URL"] + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def main(argv):
    if argv[:1] == ["list"]:
        status, items = call("GET", "/items")
        for item in items:
            print(f"{item['name']}  {item['qty']}")
        return 0
    if len(argv) == 3 and argv[0] == "add":
        try:
            qty = int(argv[2])
        except ValueError:
            print("refused: qty must be a whole number", file=sys.stderr)
            return 1
        status, body = call("POST", "/items", {"name": argv[1], "qty": qty})
        if status == 201:
            print(f"added {body['name']} x{body['qty']}")
            return 0
        print(f"refused: {body.get('error', status)}", file=sys.stderr)
        return 1
    print("usage: python3 -m stock list | add NAME QTY", file=sys.stderr)
    return 2
