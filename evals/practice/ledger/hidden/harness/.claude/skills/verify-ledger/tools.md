# Ledger developer tools

Use these commands for debugging, investigation, or verification. A read reports current state; it does not by itself prove a feature works.

## Is the ledger up and running the code on disk?

Use when: before driving the app by hand or running a check, or when a check stopped with "not ready".

Run from the project root:

`python3 .claude/skills/verify-ledger/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8071/health"`

- Inputs: none.
- Environment: an instance started with the Start command in `settings.md`; the launch record in `evidence/launch/`.
- Permissions: read-only.
- Result: prints `ready` and the loaded code's commit as JSON, exit 0.
- Failure: exit 1 with one reason per line (no instance, process gone, code on disk changed since launch, health probe failing); exit 2 when it could not tell. Start the app with the Start command, or restart it after editing code.
- Limits: says the process is up on the recorded code; says nothing about the data in it.

Help: `python3 .claude/skills/verify-ledger/scripts/framework/vf.py doctor --help`.

## What does the database say about an account?

Use when: checking a balance or an account's transactions after driving the API, or re-checking a verdict by hand.

Run from the project root:

`python3 .claude/skills/verify-ledger/scripts/probe.py account 1`

- Inputs: the account ID; `transactions <id>` lists its transactions newest first.
- Environment: the database at `data/ledger.db` under the project root (or `LEDGER_DB`); the app need not be running.
- Permissions: read-only; opens the database in read-only mode and imports no app code.
- Result: one JSON object: the account row, or `{"transactions": [...]}`; `--full` adds every column.
- Failure: exit 1 with `{"not_found": ..., "hint": ...}` when the account has no row; exit 2 with `STOPPED: <reason>` when the database is missing or unreadable.
- Limits: reports stored state only, never what the API would answer.

Help: `python3 .claude/skills/verify-ledger/scripts/probe.py --help`.
