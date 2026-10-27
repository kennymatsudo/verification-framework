# Relay tools

Written by `vf.py tools` from the tools in harness.json; edit the entry there and run it again. A read reports current state; it does not by itself prove a feature works.

## doctor

Use when: before running a check, to confirm relay is runnable and see which checkout the checks will run from.

Run from the project root:

`python3 .claude/skills/verify-relay/scripts/doctor.py`

- Inputs: none; the checkout comes from `VERIFY_CHECKOUT_RELAY`, which vf.py run sets (the scratch copy during a planned break).
- Environment: Python 3; `VERIFY_CHECKOUT_RELAY` when vf.py run set it, else this checkout.
- Permissions: read-only.
- Result: prints `relay ready`, the version, and that checkout's code state as JSON, exit 0.
- Failure: exit 1 when the checkout has no runnable relay, with the reason; exit 2 when it could not tell.
- Limits: says the tool runs; proves nothing about what it converts.

Help: `python3 .claude/skills/verify-relay/scripts/doctor.py --help`

## probe

Use when: reading an output file a check or a person produced, to re-check a verdict by hand.

Run from the project root:

`python3 .claude/skills/verify-relay/scripts/probe.py output out.json`

- Inputs: the output file's path.
- Environment: none.
- Permissions: read-only; parses the file and loads no relay code.
- Result: one JSON object: the row count, the total, and the rows (`--full` for every field).
- Failure: exit 1 with `{"not_found": ...}` when the file does not exist; exit 2 with `STOPPED: <reason>` when it is not valid JSON.
- Limits: reports the file's contents, never whether they are right.

Help: `python3 .claude/skills/verify-relay/scripts/probe.py output out.json --help`
