"""Append one JSON event per line to the file VERIFY_REPORT names, as the Evidence section of rules.md defines.

A check calls check() first, then step() the moment each verdict is decided, and exit() at the end.
It writes no evidence file: vf.py run builds the record from these events.
"""

import json
import os
import sys
import time
from contextlib import contextmanager

_STARTED = time.monotonic()
_FAILED = False


def _emit(event):
    path = os.environ.get("VERIFY_REPORT")
    line = json.dumps(event)
    if path:
        with open(path, "a") as handle:
            handle.write(line + "\n")
    print(line, file=sys.stderr)


def check(name, sub_features, reads="state"):
    _emit({"event": "check", "name": name, "sub_features": sub_features, "reads": reads})


def step(name, passed, sub_features=None, detail=None, evidence=None):
    global _FAILED
    event = {"event": "step", "name": name, "passed": bool(passed), "at": round(time.monotonic() - _STARTED, 3)}
    if sub_features is not None:
        event["sub_features"] = sub_features
    if detail is not None:
        event["detail"] = str(detail)
    if evidence is not None:
        event["evidence"] = evidence
    _emit(event)
    _FAILED = _FAILED or not passed
    return bool(passed)


def created(kind, ids):
    _emit({"event": "created", kind: list(ids)})


def stopped(reason):
    """Report that the run cannot reach a verdict and exit 2."""
    _emit({"event": "stopped", "reason": reason, "at": round(time.monotonic() - _STARTED, 3)})
    print(f"STOPPED: {reason}", file=sys.stderr)
    sys.exit(2)


@contextmanager
def guarded(step_name, sub_features=None):
    """Turn an exception inside one block into a failed step, so independent steps after it still run."""
    try:
        yield
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001
        step(step_name, False, sub_features, detail=f"{type(error).__name__}: {error}")


def exit():
    sys.exit(1 if _FAILED else 0)
