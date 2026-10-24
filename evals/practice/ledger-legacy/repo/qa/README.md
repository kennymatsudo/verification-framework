# QA scripts

Smoke checks for the ledger API, written over time by whoever shipped the feature. Start the server (`python3 -m ledger`), then from the repo root:

    python3 qa/run_all.py

Each script under `qa/checks/` prints `PASS` or `FAIL` and exits accordingly. `COVERAGE.md` says how much each one proves.
