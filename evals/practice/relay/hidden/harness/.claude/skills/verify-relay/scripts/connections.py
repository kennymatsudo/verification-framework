"""Where relay runs from: the checkout VERIFY_CHECKOUT_RELAY names, or this project root."""

import os
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HARNESS.parents[2]


def checkout():
    """The checkout checks run relay from: VERIFY_CHECKOUT_RELAY when vf.py run set it (the scratch copy during a
    planned break), else this project root. vf.py hands it to the doctor and every check."""
    named = os.environ.get("VERIFY_CHECKOUT_RELAY")
    return Path(named) if named else PROJECT_ROOT


def relay_command():
    return [sys.executable, "-m", "relay"]
