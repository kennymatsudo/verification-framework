# ADR 0005: A planned break proves only what it broke, run in a scratch copy of a fingerprinted check

Status: Accepted. 2026-10-21.

## Problem

A check counts as proof only once it has failed on a deliberate bug. Three things made that proof weaker than it looked. A break was a set of written steps an agent followed with nothing checking them: the app could be left running the broken copy, a worktree could miss the developer's uncommitted edits, and the edit itself was described in words, so rerunning it meant writing it again. A break that failed any step counted for every behavior its check covered; in a checkout check, skipping payment also fails the receipt step, and the receipt was credited though nobody broke it. And a break and a later pass were matched only by step names, so a check loosened inside a step kept its Verified.

## Decision

- **A framework script runs every break.** `vf.py break run <repo> "<IDs>: <what>" -- vf.py run -- <check>` makes a worktree at the commit under test, replays the developer's staged, unstaged, and untracked changes and confirms the `dirty_hash` matches, points the app at it through the settings' `Run scratch code` and `After an edit` commands, runs the check with `VERIFY_PLANNED_BREAK` set, saves the edit as `break.patch` beside the run, restores the copy whatever happened, and points the app back. While a session is open, `code_state.py` refuses ordinary code recording in that repo, so a run can't quietly pass on scratch code. `vf.py break replay` reruns a saved break.
- **Credit needs aim and a failed judging step.** Each step in the evidence names the behaviors it judges. The break names its targets before it runs. A behavior is proven only when the break was aimed at it and a step judging it failed; a knock-on failure earns nothing. `vf.py break run` appends each credited behavior to `evidence/breaks.jsonl`; nothing is written in the feature map, and `vf.py status` finds the break in the evidence.
- **The check is fingerprinted.** Every run records `harness_code`, the SHA-256 of every file under the harness's `scripts/` apart from the framework copies, plus any file the check command names, and is refused if those files change during it. A pass is proven only when every file its break fingerprinted has the same hash in the pass. A changed file makes `vf.py status` say so and name the replay.
- **The map's proof line is the agent's.** It names the check, what it reads, and an optional `Not break-tested: <reason>`.

## Options we passed on

- **Keep the steps as prose and add guards as rules.** Each guard still depends on an agent remembering it.
- **Breaks in the developer's checkout.** A crash, a file watcher, or a second agent could lose uncommitted work.
- **Credit any behavior whose own step failed.** The receipt step failed too, so the false credit stays.
- **Split every multi-behavior check into one per behavior.** Journeys whose steps depend on each other pay the setup cost once per behavior.
- **Copy the harness before a run and diff it after.** Fires after the run, catches only edits inside one session, and a copy still has to be compared with something.
- **A `Break-tested` clause in the feature map.** Two owners for one fact, and it went stale the moment a step changed.

## What changes

`rules.md` (Feature map, Checks, Evidence), the settings template's `Run scratch code` and `After an edit` lines, `break_session.py`, `code_state.py`, `vf.py run`, `validate.py`, `trust_facts.py`, the add-checks mode, USAGE.md, and internals.md.
