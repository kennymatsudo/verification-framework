# Statement

A client reads an account's transactions.

## Sub-features

- statement.newest-first: the statement lists the account's transactions newest first, each with the balance after it.

## How a user reaches it

- `GET /accounts/<id>/statement`.

## Verification plan

Source: REQUIREMENTS.md LR-8.

- statement.newest-first: post two deposits, read the statement; the second must be listed first, and each balance_after must equal the stored transaction's. Order is read from the response because the order is the behavior; balances from the database.

## How to prove it

- statement.newest-first: `python3 .claude/skills/verify-ledger/scripts/checks/statement.py`. Reads the response order and the stored transactions (what the user sees).
