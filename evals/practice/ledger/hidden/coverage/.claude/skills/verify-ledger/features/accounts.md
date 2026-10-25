# Accounts

A client opens an account and reads it back by ID.

## Sub-features

- accounts.open: opening an account returns its new ID, and the account reads back with a zero balance.
- accounts.unknown-404: reading an account that does not exist answers 404.

## How a user reaches it

- `POST /accounts` and `GET /accounts/<id>`.

## Verification plan

Source: REQUIREMENTS.md LR-1 and LR-2.

- accounts.open: open an account through the API; read the stored row for its name and zero balance, then read it back through the API. Proves stored state and the API answer.
- accounts.unknown-404: read an ID with no stored row; expect 404 and still no row.

## How to prove it

- accounts.open: `python3 .claude/skills/verify-ledger/scripts/checks/accounts.py`. Reads the account row (state).
- accounts.unknown-404: `python3 .claude/skills/verify-ledger/scripts/checks/accounts.py`. Reads the account row (state).
