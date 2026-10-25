# Verification notes

## Setup: verify-ledger

- Target: the ledger HTTP API in this repo, started locally from the checkout with `python3 -m ledger` on port 8071; no UI, no external services.
- Findings: README.md:9 gives the start command and port; README.md:11 names `GET /health` as the ready signal; ledger/server.py:95 reads `LEDGER_PORT` and `LEDGER_DB`; REQUIREMENTS.md holds the agreed behavior with IDs LR-1 to LR-8; an agent can start the app with only this checkout.
- Looked in: README.md, REQUIREMENTS.md, ledger/server.py, ledger/store.py, tests/; no Makefile, compose file, or package scripts.
- Blocker: none
- Next action: none
- Doctor proof: saved output in evidence/doctor/setup.txt: ready after Start (exit 0), not ready after Stop (exit 1), on the commit recorded there.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Concurrent transfers between the same two accounts.
