# Orders feature map

Open the file for the feature you changed. Follow `../rules.md` for every proof.
Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
See each check's latest run in [the recordings page](../recordings.html).

## Baseline

- Start: `python3 .claude/skills/verify-orders/scripts/framework/vf.py start --until "curl -sf http://127.0.0.1:8073/health" -- python3 -m orders`. Ready when `python3 .claude/skills/verify-orders/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8073/health"` exits 0. Stop: `python3 .claude/skills/verify-orders/scripts/framework/vf.py stop`.
- Data: an empty SQLite database the service creates at `data/orders.db`, and the shared outbox at `../../queue/outbox.jsonl`; checks place their own orders.
- Isolation: one instance per machine on port 8073; never drive one you did not start. Never run the mailer without the user's approval: it sends real mail.

## Features

None yet.
