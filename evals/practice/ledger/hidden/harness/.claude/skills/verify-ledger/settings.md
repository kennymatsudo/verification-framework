# Ledger verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: ready

## Workflow

- Requirements source: REQUIREMENTS.md

## Repos

- ledger: .

List every repo whose code a check runs, including this repo when it owns running code. A single-repo harness has one line, such as `- app: .`.

## Commands

- Start: python3 .claude/skills/verify-ledger/scripts/framework/vf.py start --checkout ledger={checkout:ledger} --until "curl -sf http://127.0.0.1:8071/health" -- env PYTHONPATH={checkout:ledger} python3 {checkout:ledger}/ledger/server.py
- Stop: python3 .claude/skills/verify-ledger/scripts/framework/vf.py stop
- Doctor: python3 .claude/skills/verify-ledger/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8071/health"
- Ready line: ready
- Probe: python3 .claude/skills/verify-ledger/scripts/probe.py
- Reloads: no

Every command runs from the project root (the repo's top folder). The app runs the checkout's files directly and does not reload on edit (Reloads: no), so the framework launcher starts it from `{checkout:ledger}`, records the code it loaded, and restarts it from the scratch copy for a planned break. The agent may start and stop the app; it needs no login or credentials. Data lives in `data/ledger.db` under the project root, which the launched process creates; `.gitignore` keeps it out of the repo. The probe reads that file read-only without importing app code. Start runs `server.py` from `{checkout:ledger}` with that checkout first on `PYTHONPATH`, from the project root, so a planned break's scratch copy is the code that loads while `data/ledger.db` stays here; `python3 -m ledger` would import this checkout's package instead. Nothing here reaches an external or shared system.
