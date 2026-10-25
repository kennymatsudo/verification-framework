# Kiosk verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: ready

## Workflow

- Requirements source: REQUIREMENTS.md

## Repos

- kiosk: .

## Commands

- Start: python3 .claude/skills/verify-kiosk/scripts/framework/vf.py start --until "curl -sf http://127.0.0.1:8072/api/health" -- node server.js
- Stop: python3 .claude/skills/verify-kiosk/scripts/framework/vf.py stop
- Doctor: python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health"
- Ready line: ready
- Probe: node .claude/skills/verify-kiosk/scripts/probe.js
- Run scratch code: python3 .claude/skills/verify-kiosk/scripts/framework/vf.py stop && python3 .claude/skills/verify-kiosk/scripts/framework/vf.py start --checkout {repo}={checkout} --until "curl -sf http://127.0.0.1:8072/api/health" -- node {checkout}/server.js
- After an edit: python3 .claude/skills/verify-kiosk/scripts/framework/vf.py stop && python3 .claude/skills/verify-kiosk/scripts/framework/vf.py start --checkout {repo}={checkout} --until "curl -sf http://127.0.0.1:8072/api/health" -- node {checkout}/server.js

Every command runs from the project root. The server runs the checkout's files directly, so the framework launcher starts it and records the code it loaded; `server.js` serves `public/` from its own folder on every request, so a scratch checkout serves its own page files, and the server itself needs a restart after an edit. The agent may start and stop it; no login. Orders live in `data/orders.json` under the project root, which `.gitignore` keeps out of the repo. Checks drive the page with Playwright's bundled Chromium (`node -e "require('playwright')"` must work) and read orders from the data file, never through the server. Nothing here reaches an external or shared system.
