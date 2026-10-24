"""Drive the ledger the way its clients do: plain HTTP requests to the running server."""

import json
import urllib.error
import urllib.request

from connections import BASE_URL


def call(method, path, body=None):
    """(status, decoded JSON) for one request. A connection failure raises, so a check can stop rather than fail."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def open_account(name):
    return call("POST", "/accounts", {"name": name})


def post_transaction(account_id, amount, memo=""):
    return call("POST", f"/accounts/{account_id}/transactions", {"amount": amount, "memo": memo})


def transfer(from_id, to_id, amount):
    return call("POST", "/transfers", {"from": from_id, "to": to_id, "amount": amount})


def get_account(account_id):
    return call("GET", f"/accounts/{account_id}")


def statement(account_id):
    return call("GET", f"/accounts/{account_id}/statement")
