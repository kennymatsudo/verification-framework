# Kiosk feature map

Open the file for the feature you changed. Follow `../rules.md` for every proof.
Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
See each check's latest run, and watch recorded ones, in [the recordings page](../recordings.html).

## Baseline

- Start: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py start --until "curl -sf http://127.0.0.1:8072/api/health" -- node server.js`. Ready when `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health"` exits 0. Stop: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py stop`.
- Data: `data/orders.json`, created on the first order; checks read back the order they placed by number.
- Isolation: one instance per machine on port 8072; never drive one you did not start.

## Features

None yet.
