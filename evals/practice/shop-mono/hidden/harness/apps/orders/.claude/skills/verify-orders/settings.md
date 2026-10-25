# Orders verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: ready

## Workflow

- Requirements source: REQUIREMENTS.md

## Repos

- orders: .

The project root is `apps/orders`, this app's folder in the monorepo, so `.` covers only the orders code. The mailer under `../mailer` is not listed: no check runs its code, and running it sends real mail. A check that does run it must add `- mailer: ../mailer` here first.

## Commands

- Start: python3 .claude/skills/verify-orders/scripts/framework/vf.py start --until "curl -sf http://127.0.0.1:8073/health" -- python3 -m orders
- Stop: python3 .claude/skills/verify-orders/scripts/framework/vf.py stop
- Doctor: python3 .claude/skills/verify-orders/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8073/health"
- Ready line: ready
- Probe: python3 .claude/skills/verify-orders/scripts/probe.py
- Run scratch code: python3 .claude/skills/verify-orders/scripts/framework/vf.py stop && python3 .claude/skills/verify-orders/scripts/framework/vf.py start --checkout {repo}={checkout} --until "curl -sf http://127.0.0.1:8073/health" -- env PYTHONPATH={checkout} python3 {checkout}/orders/server.py
- After an edit: python3 .claude/skills/verify-orders/scripts/framework/vf.py stop && python3 .claude/skills/verify-orders/scripts/framework/vf.py start --checkout {repo}={checkout} --until "curl -sf http://127.0.0.1:8073/health" -- env PYTHONPATH={checkout} python3 {checkout}/orders/server.py

Every command runs from `apps/orders`. The orders server runs the checkout's files directly and needs a restart after an edit, so the framework launcher starts it and records the code it loaded; scratch code runs the scratch checkout's `server.py` with that checkout first on `PYTHONPATH`, from this folder, so it keeps writing `data/orders.db` and the shared outbox `../../queue/outbox.jsonl` here. The agent may start and stop it. The mailer is not started by the harness: `node ../mailer/worker.js --once` sends real mail through the team relay (`../../mail-sink`), so anything that runs it is an action with a shared side effect and needs the user's approval for that run.
