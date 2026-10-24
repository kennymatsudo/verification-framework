# Ledger feature map

Open the file for the feature you changed. Follow `../rules.md` for every proof.
Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
See each check's latest run in [the recordings page](../recordings.html).

## Baseline

- Start: `python3 .claude/skills/verify-ledger/scripts/framework/vf.py start --until "curl -sf http://127.0.0.1:8071/health" -- python3 -m ledger`. Ready when `python3 .claude/skills/verify-ledger/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8071/health"` exits 0. Stop: `python3 .claude/skills/verify-ledger/scripts/framework/vf.py stop`.
- Data: an empty SQLite database the app creates at `data/ledger.db`; every check opens its own accounts.
- Isolation: one instance per machine on port 8071; never drive one you did not start.

## Features

None yet.
