# Stock tools

Written by `vf.py tools` from the tools in harness.json; edit the entry there and run it again. A read reports current state; it does not by itself prove a feature works.

## doctor

Use when: before running the client by hand or running a check, or when a check stopped with "not ready".

Run from the project root:

`python3 .claude/skills/verify-stock/scripts/api_server.py doctor`

- Inputs: none; `start` builds the API from the api checkout and starts it, `start --restart` restarts it, and `--checkout api=PATH` builds from another checkout (break sessions use it).
- Environment: Go; the api checkout `stack.env` names; an instance started by `start`.
- Permissions: `doctor` is read-only; `start` builds into the api checkout's `bin/` and starts a process.
- Result: `stock ready` and the loaded code's state as JSON, exit 0, only when the process is up, the code on disk matches the launch record, and `/version` equals the checkout's commit and uncommitted-code fingerprint.
- Failure: exit 1 with the reason (no instance, process gone, code changed, stale build); exit 2 when it could not tell.
- Limits: proves which code the API runs; says nothing about the client or the data.

Help: `python3 .claude/skills/verify-stock/scripts/api_server.py doctor --help`

## probe

Use when: checking stored items after driving the client, or re-checking a verdict by hand.

Run from the project root:

`python3 .claude/skills/verify-stock/scripts/probe.py items`

- Inputs: none; `item NAME` prints one item.
- Environment: the data file at `data/stock-items.json` under the project root, where `start` points the API; the API need not be running.
- Permissions: read-only; parses the file and loads no API or client code.
- Result: one JSON object with the stored items.
- Failure: exit 1 with `{"not_found": ...}` when the item (or the file) does not exist; exit 2 with `STOPPED: <reason>` when the file is not JSON.
- Limits: reports stored state only, never what the client printed.

Help: `python3 .claude/skills/verify-stock/scripts/probe.py items --help`
