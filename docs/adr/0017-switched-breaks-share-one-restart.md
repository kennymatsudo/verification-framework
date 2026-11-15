# ADR 0017: Breaks behind a switch share one restart

Status: Proposed. 2026-11-15. Prototyped in `vf.py break` and run on the ledger practice repo; no skill tells an agent to use it yet.

## Problem

A planned break is an edit to the app's code, so an app that doesn't reload restarts for every break: N breaks cost N+1 restarts in place and N+2 in a scratch copy. On the one slow app measured ([ADR 0015](0015-break-in-the-runs-own-copy-and-credit-only-a-clean-catch.md)), three breaks took 50 minutes and 38 of them were restarts. The advice so far is to make the restart cheap, which a stack that boots in ten minutes can't follow. Putting several breaks in one run was built and rejected: with more than one break live, which break caused a failure rests on the label the agent wrote.

## Decision

- **One edit holds every break, each behind a gate.** `vf.py break start` prints the session's switch file. A gate reads that file when the behavior runs and breaks it only while the file holds the gate's own name. The file lives in the repo's private Git folder, outside the code, so flipping it changes no fingerprint.
- **The framework flips the switch, one break at a time.** `vf.py break run <repo> "<IDs>: <what>" --switch <name> -- <check>` restarts the app only when the copy's code differs from what the last switched run loaded, writes the name, runs the check, writes `off`, and leaves the edit in place. The file holds one name, so exactly one break is live in any run, and the clean-catch rule of ADR 0015 is unchanged.
- **A switched break counts only beside a control.** `vf.py break control <repo> -- <check>` runs the check to its end with the switch `off` and records it with `break_control`. `vf.py status` credits a switched break only when an accepted control of the same check passed on the same code and the same harness code, and ran every step that caught the break. The break and its control then differ in the switch alone.
- **A control is neither a pass nor a break.** It ran on edited code, so no verdict, runs page, or demo listing treats it as a run of the code under test.
- **The file always exists while a session is open.** A gate that only tests for the file is live during the control, fails it, and earns nothing. A gate the app read once at boot never fires, so its break is missed and earns nothing.
- **A break that can't be gated runs as before.** Boot-time code, a migration, or a browser bundle can't read a file at request time; such a break takes its own restart, in a run without `--switch`, before the first switched run or in another session.

N switched breaks cost one restart for the edit, plus the session's own: 2 in place, 3 in a scratch copy, whatever N is.

## Options we passed on

- **Several breaks live in one run.** Rejected on 2026-11-01: credit would rest on the agent's labels.
- **One app instance per break, side by side.** The slow stack is the one that can't run twice on one machine.
- **Fault injection outside the app (a proxy, a deleted row).** It shows the check notices a missing effect, not that it notices the code regressing, and it sits close to forging events.
- **Break only a sample of checks.** A Verified line would stop meaning break-tested.
- **An environment variable as the switch.** A running app can't see it change.
- **Trace which harness files a check loads, to replay fewer breaks after a shared edit.** Language-specific, and replaying N switched breaks now costs one restart.
- **Skip the control and trust the gate.** A gate that is live when off, or changes the code beside it, would pass as a break.

## What changes

Done in the prototype: `break_session.py` (`run --switch`, `control`, the switch file, `armed_tree` in the session), `vf.py run` (`planned_break.switch`, `break_control`), `validate.py` (`switch_control`, the control rule in `check_break`, controls left out of passing runs), `replay.py` and `demo.py` (controls left out), `tests/switched_breaks.py`, run by `tests/test_practice_ledger.py` on the ledger practice repo, `docs/internals.md`.

On acceptance: `rules.md` (Checks, Evidence, Reporting; Rules version 10) and every mode's `--written-for`; `references/harness.md`; the add-checks and verify-pr modes, whose one break preview names each break's switch or says why it can't be gated; `smells.py` (a harness script that reads the switch file); `trust_facts.py`; USAGE.md and `docs/architecture.md`; an eval case that fails when an agent restarts a slow app once per gateable break.
