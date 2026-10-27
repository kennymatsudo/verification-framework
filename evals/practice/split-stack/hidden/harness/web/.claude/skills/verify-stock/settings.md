# Stock verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: ready

## Workflow

- Requirements source: REQUIREMENTS.md

## Repos

- web: .
- api: env:stack.env:API_CHECKOUT

The stock command in this repo drives the Stock API from the `api` repo, checked out where `stack.env`'s `API_CHECKOUT` says (`../api` by default); each developer's path stays in their own `stack.env`.

## Commands

- Start: python3 .claude/skills/verify-stock/scripts/api_server.py start --restart --checkout api={checkout:api}
- Stop: python3 .claude/skills/verify-stock/scripts/framework/vf.py stop
- Doctor: python3 .claude/skills/verify-stock/scripts/api_server.py doctor
- Ready line: stock ready
- Probe: python3 .claude/skills/verify-stock/scripts/probe.py
- Reloads: no

Every command runs from this repo's top folder, the project root. The API is a compiled Go program, so the launcher alone cannot say which code it runs: `api_server.py start --checkout api={checkout:api}` builds it from the api checkout (the scratch copy during a planned break) with the checkout's commit and uncommitted-code fingerprint stamped into `/version`, then starts it through the framework launcher with its data at `data/stock-items.json` here; `api_server.py doctor` runs the launcher's doctor and then compares `/version` with the api checkout's current code state. It needs a rebuild to run other code (Reloads: no). The agent may start and stop the API; it needs Go and nothing else. The checks run `python3 -m stock` from this checkout, so a break session on the web repo cannot run the client from a scratch copy; breaks are supported on the api repo. Nothing here reaches an external or shared system.
