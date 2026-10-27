# Verification notes

## Setup notes

Every command runs from the project root (the repo's top folder). The app runs the checkout's files directly and does not reload on edit (Reloads: no), so the framework launcher starts it from `{checkout:ledger}`, records the code it loaded, and restarts it from the scratch copy for a planned break. The agent may start and stop the app; it needs no login or credentials. Data lives in `data/ledger.db` under the project root, which the launched process creates; `.gitignore` keeps it out of the repo. The probe reads that file read-only without importing app code. Start runs `server.py` from `{checkout:ledger}` with that checkout first on `PYTHONPATH`, from the project root, so a planned break's scratch copy is the code that loads while `data/ledger.db` stays here; `python3 -m ledger` would import this checkout's package instead. Nothing here reaches an external or shared system.

## Known failing checks

- transactions.refuse-overdraft fails on current code: `ledger/store.py` lets a withdrawal take the balance below zero, which REQUIREMENTS.md LR-4 forbids. Tracked as LEDGER-41. The check keeps the requirement's expectation.

## Where a pass can mislead

- The statement check reads the API response for order, since the order is the behavior; balances come from the database.

## Untested cases

- Concurrent transfers between the same two accounts.
