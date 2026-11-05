#!/usr/bin/env bash
# Builds this case's workspace in the current folder: the practice repo as a Git repository and whatever the case
# says was already done. claude plugin eval runs it with --scaffold; evals/run.py does the same without it.
set -eu
exec python3 "$(dirname "$0")/../../run.py" scaffold --case "$(basename "$(dirname "$0")")" --into "$PWD"
