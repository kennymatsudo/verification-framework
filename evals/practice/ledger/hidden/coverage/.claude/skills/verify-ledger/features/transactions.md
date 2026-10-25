# Transactions

A client deposits into or withdraws from an account.

## Sub-features

- transactions.deposit: a deposit raises the stored balance by the amount, and the stored balance equals the sum of the account's transactions.
- transactions.refuse-overdraft: a withdrawal that would take the balance below zero is refused with 409 and leaves the balance unchanged.

## How a user reaches it

- `POST /accounts/<id>/transactions` with a positive (deposit) or negative (withdrawal) amount.

## Verification plan

Source: REQUIREMENTS.md LR-3 and LR-4.

- transactions.deposit: deposit through the API; read the stored balance and the stored transactions. Proves stored state, not the response body.
- transactions.refuse-overdraft: withdraw more than the balance; expect 409 "insufficient funds" and the stored balance unchanged. The requirement is the expectation even though the current code allows the overdraft (LEDGER-41).

## How to prove it

- transactions.deposit: `python3 .claude/skills/verify-ledger/scripts/checks/deposit.py`. Reads the account row and transactions (state).
- transactions.refuse-overdraft: `python3 .claude/skills/verify-ledger/scripts/checks/overdraft.py`. Reads the account row (state). Not break-tested: fails on current code (LEDGER-41).
