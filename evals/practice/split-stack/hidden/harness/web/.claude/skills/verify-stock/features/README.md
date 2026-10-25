# Stock feature map

Open the file for the feature you changed. Follow `../rules.md` for every proof.
Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
See each check's latest run in [the recordings page](../recordings.html).

## Baseline

- Start: `python3 .claude/skills/verify-stock/scripts/api_server.py start`. Ready when `python3 .claude/skills/verify-stock/scripts/api_server.py doctor` exits 0. Stop: `python3 .claude/skills/verify-stock/scripts/framework/vf.py stop`.
- Data: `data/stock-items.json` under the project root, created on the first add; checks add items with unique names.
- Isolation: one API per machine on port 8075; never drive one you did not start.

## Features

None yet.
