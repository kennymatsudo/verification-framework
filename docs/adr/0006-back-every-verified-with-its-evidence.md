# ADR 0006: Back every Verified with its evidence

Status: Accepted. 2026-10-16.

## Problem

The rules said a Verified result needs a passing, break-tested check on the recorded commit, but nothing compared a claim with what actually ran. Current models more often claim work is proven when it isn't than cheat on a check, so an overstated report was the likeliest way a harness would mislead. In a pilot, an agent added and renamed steps in a check after its planned break ran, then reported Verified. And each harness's agent wrote its own logic for which code ran: three practice runs produced three versions, one of which hardcoded `main` as the default branch and would silently mislabel every result on a `master` or `develop` repo.

## Decision

- **One line per result.** Each result in `status.md`'s Latest results starts with the sub-feature and its verdict. A Verified line names each repo's commit and cites its evidence file. `check.py` fails the line unless that file passed, covers the sub-feature, and records those commits, and the map's proof for it is break-tested. A cited file that is absent is a warning by default, since teams may keep evidence out of Git; skills that record results run `check.py --require-evidence` right after, where it is an error. A rejected line is corrected to match the evidence, never the reverse.
- **A planned break proves the steps that failed in it.** The proof line cites the break's evidence file. A Verified line needs that break to have failed, and every step that failed in it to still be in the passing run, by name. Renaming, removing, or changing one of those steps means rerunning the break. A step added later only makes the check stricter and needs no new break; a claim only that step covers stays a noted gap. Step names stay the same on every run, with changing values in the step's detail.
- **One script reads Git state.** `code_state.py` is copied unchanged into every harness beside `check.py`. It reads `settings.md`'s repos and prints each one's `code` entry as JSON, sharing `check.py`'s dirty test. It reports `null` for anything it can't establish, such as a default branch or a detached HEAD's branch, and stops when a repo is missing. `--checkout <repo>=<path>` reports a scratch worktree for a planned break. Harness tools call it rather than Git. Which code a running process loaded stays the doctor's job, since that depends on how each app starts.

## Options we passed on

- **Absent evidence is always an error.** Fresh checkouts without tracked evidence would fail the setup gate.
- **Absent evidence is always a warning.** An agent could cite a file that was never written.
- **Generate results from evidence.** Removes the claim, but loses the plain-language limits a person writes beside each result.
- **Every step in the passing run must have run in the break.** Reruns that teach nothing, since a step that passes during a break proves nothing about catching a fault.
- **Compare the check file's date with the break's.** Git checkouts reset file dates, so every fresh clone would fail.
- **Rule text only, for breaks or Git state.** The agent that changed the check judges whether it matters, and practice runs showed Git logic drifts silently.
- **Store each repo's default branch in settings.** The clone answers it in most repos; revisit if `null` shows up often.

## What changes

`rules.md` (Evidence, Checks, Code under test, and the feature map's proof line), `check.py` and its tests, the new `code_state.py`, the doctor guide, add-feature-checks' run recorder and break steps, and the skills that record results. A step whose logic changes but whose name doesn't still relies on the agent rerunning the break; `check.py` can't see that.
