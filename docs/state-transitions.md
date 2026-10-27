# State transitions

Where a harness, a behavior's entry (the part of its feature file that says how it is proven), a run record, and a behavior's result can be, and what moves each one. The words match `rules.md` and the output of `vf.py status`.

## A behavior's result

`vf.py status` computes one line per behavior from its entry, the accepted evidence, and any Not verified records. `vf.py validate` rejects any Verified line that `status` wouldn't write now, so one written by hand doesn't survive.

```mermaid
stateDiagram-v2
    direction TB

    state "Not verified" as NV {
        state "No check yet" as none
        state "Unreachable" as unreachable
        state "No run yet" as norun
        state "Run stopped" as stopped
        state "Passed but not break-tested" as notbroken
        state "Pass not proven" as notproven
        state "Standing record" as record
    }
    state "Failed" as failed
    state "Verified" as verified

    [*] --> none: behavior added to the map
    none --> norun: check built
    none --> unreachable: entry says unreachable
    unreachable --> norun: route found, check built

    norun --> failed: run failed
    norun --> stopped: run reached no verdict
    norun --> notbroken: run passed, no planned break yet
    norun --> notproven: run passed, but its record or break disagrees
    norun --> verified: run passed, newest break failed a step that judges it

    notbroken --> verified: planned break fails a judging step
    notproven --> verified: rerun or replayed break, records agree
    failed --> verified: later run passes with proof intact
    verified --> failed: later run fails
    verified --> notproven: harness code or a judging step changed
    verified --> notbroken: break record removed from this machine
```

**Standing record** has no arrows because it can come from anywhere: `vf.py not-verified` puts any behavior with a check into it, whatever its result was, because `status` looks at those records before it looks at the runs. A later accepted run lifts it (with `--until-break`, a later planned break too), and the result is whatever that run earns. Every "run" above means an accepted run of a check covering the behavior.

What does **not** move a result:

- A refused run. `vf.py run` renames it `<name>.json.refused` and nothing can cite it.
- A planned-break run. It proves the check and never counts as a run of the code under test.
- A hand edit to `status.md`. `vf.py run`, `vf.py status`, and `vf.py not-verified` all rewrite it.

## A behavior's entry

Each behavior is one entry under `behaviors` in its feature file. The entry decides whether a pass can ever become Verified. Whether the check was break-tested lives in the evidence, not the entry.

```mermaid
stateDiagram-v2
    direction LR
    state "words only" as none
    state "unreachable: blocker, tried" as unreachable
    state "check, reads, optional not_break_tested" as command

    [*] --> none
    none --> unreachable: add-checks mode finds no route
    none --> command: check built
    unreachable --> command: route found
    command --> command: agent removes not_break_tested once a break caught it
```

The agent writes every form. Nothing in the entry says Break-tested: `vf.py status` computes that from the evidence and nothing else may claim it.

## A run record

Every check runs through `vf.py run`, which decides whether the record counts.

```mermaid
stateDiagram-v2
    direction LR
    state "Reported by the check" as written
    state "Accepted" as accepted
    state "Refused (name.json.refused)" as refused

    [*] --> written: check exits, vf.py run builds the record from its events
    written --> accepted: well formed, verdict matches exit code, code unchanged during the run
    written --> refused: a REFUSED line names a problem
    accepted --> [*]: status.md refreshed
    refused --> [*]: fix what the REFUSED lines name and rerun
```

Before any of this, `vf.py run` runs the doctor and stops with exit code 2 when the app isn't ready, so no record is written at all.

## A harness's setup

The `setup` block of `harness.json` carries the status and the record setup resumes from. `vf.py validate` exits 2 while the status is `incomplete`, with the resume action, and nothing may drive the app until it's `ready`.

```mermaid
stateDiagram-v2
    direction LR
    state "No harness" as none
    state "incomplete" as incomplete
    state "ready" as ready

    [*] --> none
    none --> incomplete: setup mode creates the layout and copies rules.md
    incomplete --> incomplete: blocker recorded with the next action
    incomplete --> ready: doctor exits 0 against the real app, setup record written
    ready --> ready: vf.py run reruns the doctor before every check
```

Ready means setup was once proven, not that the app is up now. Nothing moves a harness back to `incomplete`. A `rules.md` that no longer matches the hash in `framework.sha256` makes `vf.py validate` exit 1 before it checks anything else, and `vf.py sync` refuses to overwrite an edited framework copy or downgrade the rules.
