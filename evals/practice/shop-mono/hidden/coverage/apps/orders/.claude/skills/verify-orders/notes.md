# Verification notes

## Setup: verify-orders

- Target: the orders service under apps/orders in the shop monorepo, started locally with `python3 -m orders` on port 8073, and its hand-off to the mailer through the shared outbox; the mailer sends real mail and is not run by the harness.
- Findings: apps/orders/README.md:9 gives the start command and port; orders/server.py:73 reads `ORDERS_PORT`, `ORDERS_DB`, and `SHOP_OUTBOX`; README.md:12 at the repo root says the mail-sink folder forwards to the team's shared inbox; REQUIREMENTS.md holds SR-1 to SR-3.
- Looked in: README.md, apps/orders/README.md, apps/orders/REQUIREMENTS.md, apps/orders/orders/, apps/mailer/README.md, apps/mailer/worker.js.
- Blocker: none
- Next action: none
- Doctor proof: saved output in evidence/doctor/setup.txt: ready after Start (exit 0), not ready after Stop (exit 1), on the commit recorded there.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- The mailer's sending (SR-3) has no check: running it sends real mail to the team's inbox, so it needs the user's approval for each run.
