---
name: setup-verification
description: >-
  Create or resume an app's verification harness and prove its environment is
  ready. Use for "set up verification for this app" or "resume verification setup".
  Ends with a ready harness, even with no feature checks. Use add-feature-checks
  to create checks for a behavior, add-tools to add probes and actions, and
  audit-coverage to keep them current.
disable-model-invocation: true
---

# Set up verification

You own a verification harness whose startup and readiness have been proven against the real app. Probes and actions belong to add-tools, and feature checks to add-feature-checks.

## 1. Find the target and harness

Start from the app or system the user named; for a named feature, find the app that serves it. Confirm the target from project instructions and workspace or setup configuration, not a directory name.

Glob `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) and read each candidate's app scope. Don't use an unrelated harness just because it is the only one. When the target or harness is still ambiguous, ask one question with a recommendation.

For a matching harness, read its Setup record in `status.md` following `references/setup.md`.

- **No matching harness:** start one, then steps 3 to 5.
- **Incomplete setup:** resume steps 3 to 5; a missing startup command is a discovery gap.
- **Ready harness:** run its doctor and report readiness.

Done when the target and harness are established, or the reply names the ambiguity and the answer needed.

## 2. Start the harness

Confirm verify-change is available in the session's installed skills. If it is missing, stop before creating the harness and tell the user to install it from verification-framework alongside setup-verification.

Pick the skills directory the app's folder already uses, nearest the app in a monorepo; if none, the one the current agent loads. Name the harness `verify-<app>` after the app. Copy `references/rules.md` to `rules.md`, and this skill's `scripts/validate.py`, `code_state.py`, `break_session.py`, `replay.py`, and `clip.py` into the harness's `scripts/framework/`, all unchanged; the app's own tools go in `scripts/` beside that folder.

Write `settings.md` from `references/settings.md` with Setup Status `incomplete` and only the fields already known. Write `status.md` from `references/status.md`. Write `README.md` from `references/readme.md`.

Run the harness's `scripts/framework/replay.py --recordings` to create `recordings.html`, the page where people see each check's latest run and watch recorded ones; it says no check has run yet until one does.

Done when the harness's `validate.py` exits 2 and prints the Setup record's blocker and next action.

## 3. Discover

Spawn a read-only subagent on a mid-tier model with the prompt in `references/discovery-prompt.md`, the target, and any saved findings. Spot-check two of its citations. Follow `references/setup.md` to resolve missing setup, show the setup note when one is needed, and save findings and blockers.

Done when required setup facts are sourced and any needed setup note has been shown, or the Setup record names the blocker and resume action. On a blocker, stop before completing the skeleton.

## 4. Complete the skeleton

1. Fill `settings.md` from discovery. Omit unknown required fields; never invent a command or locator.
2. Write `SKILL.md` from `references/verify-skill-template.md`.
3. Write `features/README.md` from the index in the Feature map section of `rules.md`, with an empty Features list.
4. Build the doctor in `scripts/`, following `references/doctor.md`.
5. Publish the doctor in `tools.md` using `references/tool-guide.md` and rules.md's Tool discovery requirements.

Done when the skeleton has no template placeholders, the Setup record names the remaining proof, and Status is `incomplete`. Unknown required fields return to discovery.

## 5. Prove readiness

Start the app the sourced way, or have the user start it when only they can, then run the doctor against it following its proof in `references/doctor.md`. Never start a substitute that skips the real startup path. Follow "Mark completion" in `references/setup.md` to handle startup failures and mark setup ready. Stop processes this run started; name anything still open.

Done when Status is `ready`, doctor proof is inspectable, and `validate.py` exits 0, or Status is `incomplete` with a saved blocker and resume action. If the user also asked for feature checks, then load add-feature-checks.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Edit an existing file outside the harness only when the user named it as part of this workflow or agreed to that exact edit.
- Add levels of proof, extra skills, or workflow rules only when the user asks for them.
- Create no feature tools or checks during setup. Do not change Git ignore files or decide which harness artifacts the team tracks.

Reply: in the Messages shape from `references/rules.md`. When ready: one line saying the harness is ready and every verification run first checks the app is up and running the right code; any fix the user needs on their own machine, one line; then `Next:` with two bullets, each skill written the way the user's agent invokes it: the app's verify skill, run alone to see what the harness can check or with a named change, and add-feature-checks with a feature that works today. Add nothing else: the doctor's proof and limits are in `status.md` and `tools.md`. When blocked: what blocks setup and what resumes it. If the project-instruction pointer isn't wired, end with it as the `Needs you` question, below the `Next:` bullets.
