"""Helpers the test files share."""

import subprocess


def git(path, *args):
    """Git's trimmed output for the command run in path, with a fixed identity so commits work on any machine."""
    return subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
