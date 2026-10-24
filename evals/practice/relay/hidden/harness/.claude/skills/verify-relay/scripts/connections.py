"""Where relay runs from: the checkout the pointer file names, or this project root."""

import os
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HARNESS.parents[2]
POINTER = HARNESS / "evidence" / "launch" / "checkout.txt"


def checkout():
    """The checkout checks run relay from: the pointer file's path when it exists, else the project root."""
    if POINTER.is_file():
        text = POINTER.read_text().strip()
        if text and text != ".":
            return Path(text)
    return PROJECT_ROOT


def relay_command():
    return [sys.executable, "-m", "relay"]
