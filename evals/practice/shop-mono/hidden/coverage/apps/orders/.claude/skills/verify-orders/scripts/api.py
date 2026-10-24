"""Drive the orders service the way its clients do: plain HTTP requests."""

import json
import urllib.error
import urllib.request

from connections import BASE_URL


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def place_order(email, items):
    return call("POST", "/orders", {"email": email, "items": items})
