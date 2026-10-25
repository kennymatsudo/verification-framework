# Orders developer tools

Use these commands for debugging, investigation, or verification. A read reports current state; it does not by itself prove a feature works.

## Is the orders service up and running the code on disk?

Use when: before driving the API by hand or running a check, or when a check stopped with "not ready".

Run from the project root:

`python3 .claude/skills/verify-orders/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8073/health"`

- Inputs: none.
- Environment: an instance started with the Start command in `settings.md`; the project root is `apps/orders`.
- Permissions: read-only.
- Result: prints `ready` and the loaded code's commit as JSON, exit 0.
- Failure: exit 1 with one reason per line; exit 2 when it could not tell. Start the service with the Start command, or restart it after editing code.
- Limits: says the process is up on the recorded code; says nothing about the data in it or about the mailer.

Help: `python3 .claude/skills/verify-orders/scripts/framework/vf.py doctor --help`.

## What was stored for an order, and what is in the outbox?

Use when: checking an order after placing it, or seeing which confirmation jobs are pending.

Run from the project root:

`python3 .claude/skills/verify-orders/scripts/probe.py order 1`

- Inputs: the order ID; `outbox` lists every job in the shared outbox with its status.
- Environment: the database at `data/orders.db` under apps/orders (or `ORDERS_DB`) and the outbox at `../../queue/outbox.jsonl` (or `SHOP_OUTBOX`); the service need not be running.
- Permissions: read-only; opens the database read-only and imports no app code.
- Result: one JSON object: the order row with its lines and total, or `{"jobs": [...]}`.
- Failure: exit 1 with `{"not_found": ..., "hint": ...}` when the order has no row; exit 2 with `STOPPED: <reason>` when the database or outbox is unreadable.
- Limits: reports stored state only; a pending job says nothing about whether mail was sent.

Help: `python3 .claude/skills/verify-orders/scripts/probe.py --help`.

## Run one behavior's check

Use when: proving a behavior after a change, or reproducing a failed step by hand.

Run from the project root:

`python3 .claude/skills/verify-orders/scripts/framework/vf.py verify orders.create`

- Inputs: one or more sub-feature IDs from `features/`.
- Environment: the service started with the Start command.
- Permissions: places orders in the local database and jobs in the shared outbox file; runs no mailer, sends no mail.
- Result: one status line per ID and an evidence file under `evidence/<check>/`; `status.md` is refreshed.
- Failure: exit 1 when a step failed; exit 2 when the service was not ready.
- Limits: a pass proves only the behaviors the feature file maps to that command, on the recorded code.

Help: `python3 .claude/skills/verify-orders/scripts/framework/vf.py verify --help`.
