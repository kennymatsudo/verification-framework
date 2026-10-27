# Relay tools

Written by `vf.py tools` from the tools in harness.json; edit the entry there and run it again. A read reports current state; it does not by itself prove a feature works.

## doctor

Use when: before running a check, or after a break session, to see which checkout the checks point at.

Run from the project root:

`python3 .claude/skills/verify-relay/scripts/doctor.py`

- Inputs: none; `--point <checkout>` repoints the checks at another checkout (break sessions use it), `--point .` points back here.
- Environment: Python 3; the pointer file `evidence/launch/checkout.txt` when one exists.
- Permissions: read-only, except `--point`, which writes the pointer file.
- Result: prints `relay ready`, the version, and the pointed checkout's code state as JSON, exit 0.
- Failure: exit 1 when the pointed checkout has no runnable relay, with the reason; exit 2 when it could not tell.
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

## verify

Use when: proving a behavior after a change, or reproducing a failed step by hand.

Run from the project root:

`python3 .claude/skills/verify-relay/scripts/framework/vf.py verify convert.rows`

- Inputs: one or more sub-feature IDs from `features/`.
- Environment: Python 3; the checks run relay from the checkout the doctor points at.
- Permissions: writes only input and output files in the run's own folder.
- Result: one status line per ID and an evidence file under `evidence/<check>/`; `status.md` is refreshed.
- Failure: exit 1 when a step failed; exit 2 when relay could not run.
- Limits: a pass proves only the behaviors the feature file maps to that command, on the recorded code.

Help: `python3 .claude/skills/verify-relay/scripts/framework/vf.py verify convert.rows --help`
