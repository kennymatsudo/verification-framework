# Kiosk developer tools

Use these commands for debugging, investigation, or verification. A read reports current state; it does not by itself prove a feature works.

## Is the kiosk up and running the code on disk?

Use when: before driving the page by hand or running a check, or when a check stopped with "not ready".

Run from the project root:

`python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health"`

- Inputs: none.
- Environment: an instance started with the Start command in `settings.md`.
- Permissions: read-only.
- Result: prints `ready` and the loaded code's commit as JSON, exit 0.
- Failure: exit 1 with one reason per line; exit 2 when it could not tell. Start the app with the Start command, or restart it after editing `server.js`.
- Limits: says the server is up on the recorded code; says nothing about the page a browser has loaded.

Help: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --help`.

## What order did the kiosk store?

Use when: checking what was stored after placing an order on the page, or re-checking a verdict by hand.

Run from the project root:

`node .claude/skills/verify-kiosk/scripts/probe.js order 1`

- Inputs: the order number shown on the page; `orders` lists every stored order's number and total.
- Environment: the data file at `data/orders.json` under the project root (or `KIOSK_DATA`); the server need not be running.
- Permissions: read-only; reads the file directly and loads no server code.
- Result: one JSON object: the stored order with its lines and total, or `{"orders": [...]}`.
- Failure: exit 1 with `{"not_found": ..., "hint": ...}` when no such order is stored; exit 2 with `STOPPED: <reason>` when the file is unreadable.
- Limits: reports stored state only, never what the page showed.

Help: `node .claude/skills/verify-kiosk/scripts/probe.js --help`.

## Run one behavior's check

Use when: proving a behavior after a change, or reproducing a failed step by hand.

Run from the project root:

`python3 .claude/skills/verify-kiosk/scripts/framework/vf.py verify cart.total`

- Inputs: one or more sub-feature IDs from `features/`; the check scripts under `scripts/checks/` can also run directly through `vf.py run -- <command>`.
- Environment: the server started with the Start command; Playwright with its bundled Chromium (`node -e "require('playwright')"`).
- Permissions: places orders in the local data file only; nothing shared.
- Result: one status line per ID, an evidence file under `evidence/<check>/`, and a refreshed `status.md`. A failed run keeps its video, screenshots, console output, and failed requests in the run folder; `VERIFY_KEEP_RECORDING=1` keeps a passing run's video too.
- Failure: exit 1 when a step failed, with the step and what it found; exit 2 when the server was not ready or the page did not load.
- Limits: a pass proves only the behaviors the feature file maps to that command, on the recorded code.

Help: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py verify --help`.

## Watch how a check ran

Use when: a step failed and the detail is not enough, or a reviewer wants to see the behavior.

Run from the project root:

`python3 .claude/skills/verify-kiosk/scripts/framework/vf.py replay .claude/skills/verify-kiosk/evidence/order/<time>.json`

- Inputs: an evidence file; `recordings.html` in the harness lists every check's latest run with a Watch button where a video was kept.
- Environment: none; `vf.py clip --check` says whether this machine can cut clips and stills (optional tools).
- Permissions: read-only; writes only the replay page beside the evidence.
- Result: the replay page's path.
- Failure: exit 1 when the evidence file is missing or malformed.
- Limits: a recording shows what happened; the steps decide the verdict.

Help: `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py replay --help`.
