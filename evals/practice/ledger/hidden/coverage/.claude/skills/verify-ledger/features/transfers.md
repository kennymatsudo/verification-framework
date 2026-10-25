# Transfers

A client moves money from one account to another.

## Sub-features

- transfers.move: a transfer debits the source and credits the destination by the same amount, and both changes happen or neither does.
- transfers.refuse-overdraft: a transfer larger than the source balance is refused with 409 and changes neither account.

## How a user reaches it

- `POST /transfers`.

## Verification plan

Source: REQUIREMENTS.md LR-5 and LR-6. LR-7's daily limit is undecided and has no check.

- transfers.move: fund a source, transfer through the API; read both stored balances and the stored transfer row.
- transfers.refuse-overdraft: ask for more than the source holds; expect 409 and both stored balances unchanged.

## How to prove it

- transfers.move: `python3 .claude/skills/verify-ledger/scripts/checks/transfers.py`. Reads both account rows and the transfer row (state).
- transfers.refuse-overdraft: `python3 .claude/skills/verify-ledger/scripts/checks/transfers.py`. Reads both account rows (state).
