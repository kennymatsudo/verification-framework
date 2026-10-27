# Verification notes

## Setup notes

The project root is `apps/orders`, this app's folder in the monorepo, so `.` covers only the orders code. The mailer under `../mailer` is not listed: no check runs its code, and running it sends real mail. A check that does run it must add `- mailer: ../mailer` here first.
Every command runs from `apps/orders`. The orders server runs the checkout's files directly and needs a restart after an edit (Reloads: no), so the framework launcher starts it from `{checkout:orders}` and records the code it loaded; it runs that checkout's `server.py` with the checkout first on `PYTHONPATH`, from this folder, so a planned break's scratch copy is the code that loads while `data/orders.db` and the shared outbox `../../queue/outbox.jsonl` stay here. The agent may start and stop it. The mailer is not started by the harness: `node ../mailer/worker.js --once` sends real mail through the team relay (`../../mail-sink`), so anything that runs it is an action with a shared side effect and needs the user's approval for that run.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- The mailer's sending (SR-3) has no check: running it sends real mail to the team's inbox, so it needs the user's approval for each run.
