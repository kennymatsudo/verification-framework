# Kiosk tools

Written by `vf.py tools` from the tools in harness.json; edit the entry there and run it again. A read reports current state; it does not by itself prove a feature works.

## doctor

Use when: before driving the page by hand or running a check, or when a check stopped with "not ready".

Run from the project root:

`python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health"`

- Inputs: none.
- Environment: an instance started with the Start command in `harness.json`.
- Permissions: read-only.
- Result: prints `ready` and the loaded code's commit as JSON, exit 0.
- Failure: exit 1 with one reason per line; exit 2 when it could not tell. Start the app with the Start command, or restart it after editing `server.js`.
- Limits: says the server is up on the recorded code; says nothing about the page a browser has loaded.

Help: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health" --help`

## probe

Use when: checking what was stored after placing an order on the page, or re-checking a verdict by hand.

Run from the project root:

`node .claude/skills/verify-kiosk/scripts/probe.js order 1`

- Inputs: the order number shown on the page; `orders` lists every stored order's number and total.
- Environment: the data file at `data/orders.json` under the project root (or `KIOSK_DATA`); the server need not be running.
- Permissions: read-only; reads the file directly and loads no server code.
- Result: one JSON object: the stored order with its lines and total, or `{"orders": [...]}`.
- Failure: exit 1 with `{"not_found": ..., "hint": ...}` when no such order is stored; exit 2 with `STOPPED: <reason>` when the file is unreadable.
- Limits: reports stored state only, never what the page showed.

Help: `node .claude/skills/verify-kiosk/scripts/probe.js order 1 --help`
