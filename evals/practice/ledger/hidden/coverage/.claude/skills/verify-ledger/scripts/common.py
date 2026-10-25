"""Shared by every ledger check: path setup and a stop when the app is unreachable."""

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api  # noqa: E402
import reads  # noqa: E402
import reporter  # noqa: E402


def open_or_stop(name):
    """Open an account through the API; stop the run when the server cannot be reached."""
    try:
        status, body = api.open_account(name)
    except (urllib.error.URLError, ConnectionError) as error:
        reporter.stopped(f"the ledger did not answer: {error}")
    if status != 201 or "id" not in body:
        reporter.stopped(f"could not open a test account: {status} {body}")
    reporter.created("accounts", [body["id"]])
    return body["id"]
