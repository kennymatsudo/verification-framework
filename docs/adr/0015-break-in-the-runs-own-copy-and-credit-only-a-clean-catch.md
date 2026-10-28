# ADR 0015: Break in the run's own copy, and credit only a clean catch

Status: Proposed. 2026-10-27.

## Problem

Planned breaks cost most of a pull request verification on a large repo. In one run on a 70,000-file monorepo, three breaks took 50 minutes, and 38 of them were stack restarts. `vf.py break start` made a fresh worktree in a temporary folder and pointed the stack at it, and `end` pointed it back; under [ADR 0010](0010-start-takes-the-checkout.md) both are a Stop and Start. A new folder rebuilt every service, a tool that trusts folders one by one (direnv) refused the new path, and the run had already made its own worktree of the pull request with the stack running on it. Add-checks also opened one session per check, and a break that failed at an earlier step for an unplanned reason cost a full run.

Speeding this up exposed gaps in what a break proves. A target step that failed only because setup failed earned credit. A check that read `VERIFY_PLANNED_BREAK` could take a shorter path during a break than during a pass, and nothing flagged it.

## Decision

- **A worktree the framework made hosts the break in place.** `vf.py break worktree <repo> <path> <commit> [--branch NAME]` adds a new linked worktree and writes an ownership marker in its private Git folder. When a repo's locator points at a marked worktree with no uncommitted product code and product code still at the marker's commit, `break start` breaks there: no new worktree and no Stop and Start, after the doctor reports the app ready on it. Restarts before each break and at `end` follow `reloads` as for a scratch copy, on the same worktree, so a session of N breaks restarts the app N+1 times with `reloads` false (a scratch copy takes N+2) and never with it true (a scratch copy takes 2). A marked worktree that fails a precondition, an unreadable or foreign marker, and a marker in a main worktree are refused, never quietly copied. Unmarked worktrees always get a scratch copy.
- **Restore touches product code only, and checks the whole repo.** In place, restore resets the product paths to the start snapshot, so harness work in the worktree survives. Product code is snapshotted before the restart and after the check; if anything moved, the copy is left alone, the run's evidence is renamed `.held` so it never counts, and the session waits for `end`. `end` refuses while HEAD has moved and marks the session ending in its own field.
- **One session holds every break for a change.** Add-checks plans all breaks in one preview, each naming the step that should catch it and the earlier steps it passes through, and asks once for their total side effects only when they have real or shared ones. Verify-pr makes its worktrees with `vf.py break worktree` after settling any merge with the default branch. Every check a session credited passes once more on the restored code before it is reported.
- **Credit needs a clean catch.** A break credits a target only when every step that failed before the target's first failed judging step judges some target. A break that also breaks an earlier behavior names it as a target.
- **The framework ends a break run.** `vf.py run` stops a break run once every target has a failed judging step, or once the last step that judged a target in the latest accepted pass of the same harness code has passed: SIGINT to the check's process group, SIGKILL after 30 seconds, and `ended_early` in the record. A missed break exits 0. The weak-checks audit's `smells.py` flags a harness script that reads `VERIFY_PLANNED_BREAK` or `VERIFY_BREAK_SESSION`.
- **The Rules version rises to 8.** Break records that fail the clean-catch rule stop counting until the break runs again.

## Options we passed on

- **Break in any linked worktree the locator points at.** A developer's own work also lives in linked worktrees.
- **An `--in-place` flag.** One more option to forget; the marker already says when in place is safe.
- **Skip the doctor at an in-place start.** With `reloads` true nothing restarts before the first break, so a wrong running version would surface only after the first check ran.
- **Several breaks in one run.** Two checks that prompted this read the same message, so one break could earn another's credit.
- **Skip the restart at `end`.** The app would keep running the last break with nothing on disk to show it.

## What changes

`break_session.py`, `code_state.py` (the `ending` field), `vf.py` (`run`), `validate.py` (`break_catch`, `ended_early`), the installed `smells.py`; `rules.md` (Code under test, Checks, Evidence, Reporting, Rules version 8) and every mode's `--written-for`; `references/harness.md`; the verify-pr, add-checks, and weak-checks audit modes and `harness-components.md`; USAGE.md, `docs/internals.md`, `docs/architecture.md`, and `docs/design.md`.
