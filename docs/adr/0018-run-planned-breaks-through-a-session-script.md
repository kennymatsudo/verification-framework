# ADR 0018: Run planned breaks through a session script

Status: Accepted. 2026-10-18.

## Problem

A planned break was a set of written steps an agent followed: add a scratch worktree, edit it, run the check, remove the worktree. Nothing checked any of them. The app could be left running the broken copy, and the next ordinary verification would pass on it. A worktree starts from the last commit, so a break could run against code missing the developer's uncommitted edits. An edit could land in the developer's own checkout. The edit itself was described only in words, so rerunning a break meant writing it again from memory.

## Decision

- **A framework script runs every break.** `scripts/framework/break_session.py` is copied into every harness. `start` makes a worktree at the commit under test, replays the developer's staged, unstaged, and untracked changes, confirms its `dirty_hash` matches, and points the app at it. `run` runs the check with `VERIFY_PLANNED_BREAK` set, saves the edit as `break.patch` in the run's folder, and restores the copy whatever the check did. `end` points the app back, removes the copy, and reports any change to the developer's checkout. `replay` reruns a saved break.
- **Ordinary runs refuse while a session is open.** The session file lives in the repo's shared Git folder, which every worktree sees and nothing commits. `code_state.py`, which every run already calls, refuses a repo with an open session unless `VERIFY_PLANNED_BREAK` is set, and then reports the scratch copy. No harness writes its own guard.
- **Two settings lines.** `Run scratch code` is a command that points the app at a checkout, `per check` when each check starts the app itself, or `none`. `After an edit` is `reloads` or a restart command. `none` blocks breaks, as before.
- **One break per session for now.** add-feature-checks starts and ends a session around each break. Several breaks in one session, which saves rebuilds on slow apps, waits for a measured trial.

## Options we passed on

- **Keep the steps as prose and add the guards as rules.** Each guard would still depend on an agent remembering it.
- **Fix only the uncommitted-edits gap in the wording.** Leaves the app-left-on-scratch risk unguarded.
- **Keep the session file in `evidence/`.** Teams choose what to commit there, so a session file could be committed.
- **A guard each harness's run recorder writes.** Every harness would need its own, and one could be missed.
- **A step that waits for a person to point the app.** Agents run the script without a terminal to wait on; deferred until an app needs it.

## What changes

`rules.md` (Checks), the `settings.md` template, `validate.py`'s required settings, `code_state.py`, the new script and its tests, setup-verification's copy list and discovery prompt, add-feature-checks' break steps, USAGE.md, README.md, `docs/internals.md`, and `docs/architecture.md`. Each harness copies `break_session.py` and the new `code_state.py` and `validate.py`, and fills the two settings lines before `validate.py` accepts its settings.
