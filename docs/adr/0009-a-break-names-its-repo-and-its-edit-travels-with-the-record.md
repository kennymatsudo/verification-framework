# ADR 0009: A planned break names its repo, and its edit travels with the record

Status: Accepted. 2026-10-23.

## Problem

A planned break stays valid only while the harness code it ran is unchanged ([ADR 0008](0008-fingerprint-what-a-check-could-load.md)), so editing a shared harness file means replaying every break. Three gaps made that replay hard or unsafe:

- **The edit stayed on one machine.** `vf.py break run` saved the break's edit as `break.patch` inside the run's folder, beside the video and screenshots. Teams ignore run folders in Git because of their size, so a teammate who edited a shared harness file had nothing to replay and had to plan and write every break again.
- **The record didn't say which repo the break edited.** `vf.py break replay` relied on the person typing the right repo.
- **A break could be recorded outside a session.** `vf.py run` recorded a planned break whenever `VERIFY_PLANNED_BREAK` was set. Setting it by hand and editing the developer's own checkout produced a break that counted, with no saved edit and nothing restored afterward.

## Decision

- **The edit is saved beside the record.** `vf.py break run` writes `evidence/<check>/<time>.patch` next to `<time>.json`, outside the run folder, so a team that commits records keeps the edit too. Tracking stays the team's choice.
- **`vf.py run` takes the repo from the open break session.** When `VERIFY_PLANNED_BREAK` is set, it finds the one session this harness has open on its scratch copy and records that repo in `planned_break.repo`. With no session open, or sessions open on several repos, it stops before the check runs.
- **A break that names no settings repo proves nothing.** `validate.py` treats it like any other malformed break record.
- **`vf.py break replay` takes only the evidence file.** It reads the repo from the record.
- **The Rules version rises to 3.** Break records written before this change name no repo and keep their patch inside the run folder, so they stop counting until the break runs again.

## Options we passed on

- **A new environment variable naming the repo.** Anyone can set it by hand, as they could `VERIFY_PLANNED_BREAK`, so it would record the repo without closing the gap.
- **Infer the repo from the paths in the patch.** Paths can exist in several repos, and the record would still not say.
- **Keep accepting old break records.** Every reader of a break record would handle two shapes, and the project carries no compatibility for earlier harnesses ([ADR 0001](0001-one-harness-per-app.md)).
- **Edit the harness's Git ignore file to track run folders.** Retention is the team's call, and run folders hold videos.

## What changes

`vf.py` (`run`, `parse_planned_break`); `code_state.py` (`break_session_repo`); `break_session.py` (`run_break`, `replay`, its command line); `validate.py` (`record_problems`); `rules.md` (Break-tested, Evidence, the Rules version); the gate sentence's `--written-for` in every skill that reads a harness; `docs/internals.md`; `docs/design.md`.
