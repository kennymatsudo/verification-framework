# Set up verification

Follow this when vf runs in setup or update mode. Run it only when the person asked for this job by name in this session; otherwise offer it in one line and stop. The Guardrails in vf's `SKILL.md` apply throughout. Update means the user asked only to bring the harness's framework copies up to date.

You own a verification harness whose startup and readiness have been proven against the real app. Probes, actions, and feature checks belong to the add-tools and add-checks modes.

## 1. Find the target and harness

Start from the app or system the user named; for a named feature, find the app that serves it. Confirm the target from project instructions and workspace or setup configuration, not a directory name.

Glob `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) and read each candidate's app scope. Don't use an unrelated harness just because it is the only one. When the target or harness is still ambiguous, ask one question, with a recommendation only when the project or the request settles it.

For a matching harness, first bring its framework copies up to date by running this skill's `scripts/vf.py sync <harness>`. It replaces `rules.md`, every script in `<harness>/scripts/framework/`, and the copy of vf beside the harness that differs from the installed skill, names each file, and removes a file it recorded earlier that the framework no longer ships. A copy of this skill committed beside the harness has no `scripts/`: say that updating needs the framework installed, give the install command from the framework README, and stop. When sync stops instead:

- **Harness on a newer Rules version:** tell the user to update the installed framework skills, since copying would downgrade the harness.
- **A framework copy was edited:** show the differences it printed and ask before rerunning with `--restore`; app specifics belong in `harness.json`, and a fix to a framework script belongs in the framework.

When the user asked only to update the harness, run its `vf.py validate` and stop there: the update is done without starting the app. Otherwise read the `setup` block in its `harness.json` following `references/setup.md`.

- **No matching harness:** start one, then steps 3 to 5.
- **Incomplete setup:** resume steps 3 to 5; a missing startup command is a discovery gap.
- **Ready harness:** run its doctor and report readiness.

Done when the target and harness are established and an existing harness's framework copies match this skill's, or the reply names the ambiguity, edit, or version gap and the answer needed.

## 2. Start the harness

Pick the skills directory the app's folder already uses, nearest the app in a monorepo; if none, the one the current agent loads. Name the harness `verify-<app>` after the app. Run this skill's `scripts/vf.py sync <harness>` to copy `rules.md` and the framework scripts into the harness, unchanged, and the vf skill beside it, without its `scripts/`, so teammates who clone the repo have it without installing anything. The app's own tools go in `<harness>/scripts/`, beside `<harness>/scripts/framework/`.

Write `harness.json` from `references/harness.md` with setup `status` `incomplete`, the `setup` block filled with what discovery has found so far, and only the other fields already known. Write `notes.md` from `references/notes.md`. Write `README.md` from `references/readme.md`.

Run the harness's `scripts/framework/vf.py replay --recordings` to create `recordings.html`, the page where people see each check's latest run and watch recorded ones; it says no check has run yet until one does.

Done when the harness's `vf.py validate` exits 2 and prints the `setup` block's blocker and next action.

## 3. Discover

Spawn a read-only subagent on a mid-tier model with the prompt in `references/discovery-prompt.md`, the target, and any saved findings. Spot-check two of its citations. Follow `references/setup.md` to resolve missing setup, show the setup note when one is needed, and save findings and blockers.

Done when required setup facts are sourced and any needed setup note has been shown, or the `setup` block names the blocker and resume action. On a blocker, stop before completing the skeleton.

## 4. Complete the skeleton

1. Fill `harness.json` from discovery. Omit unknown required fields; never invent a command or locator.
2. Write `SKILL.md` from `references/verify-skill-template.md`.
3. Run the harness's `scripts/framework/vf.py status` to create `status.md`; `features/` appears when the first feature file is written.
4. Build the doctor in `scripts/`, following `references/doctor.md`.
5. Add the doctor's entry under `tools` in `harness.json` following `references/tool-guide.md` and rules.md's Tool discovery requirements, then run `scripts/framework/vf.py tools` to write `tools.md`.

Done when the skeleton has no template placeholders, the `setup` block names the remaining proof, and its `status` is `incomplete`. Unknown required fields return to discovery.

## 5. Prove readiness

Start the app the sourced way, or have the user start it when only they can, then run the doctor against it following its proof in `references/doctor.md`. Never start a substitute that skips the real startup path. Follow "Mark completion" in `references/setup.md` to handle startup failures and mark setup ready. Stop processes this run started; name anything still open.

Done when `status` is `ready`, `doctor_proof` names inspectable output, and `vf.py validate` exits 0, or `status` is `incomplete` with a saved blocker and resume action. If the user also asked for feature checks, then follow `references/mode-add-checks.md`.

## Guardrails for this mode

- Edit an existing file outside the harness only when the user named it as part of this workflow or agreed to that exact edit.
- Add levels of proof, extra skills, or workflow rules only when the user asks for them.
- Create no feature tools or checks during setup. Do not change Git ignore files or decide which harness artifacts the team tracks.

Reply: in the shape `references/messages.md` gives. When step 1 updated framework copies, open with one line naming the files replaced and any Rules version change. After an update-only request: that line, `vf.py validate`'s result, and a `Next:` bullet to run vf again to prove readiness. When ready: one line saying the harness is ready and every verification run first checks the app is up and running the right code; any fix the user needs on their own machine, one line; then `Next:` with two bullets, each skill written the way the user's agent invokes it: the app's verify skill, run alone to see what the harness can check or with a named change, and vf in add-checks mode with a feature that works today. Add nothing else: the doctor's proof and limits are in `notes.md` and `tools.md`. When blocked: what blocks setup and what resumes it. If the project-instruction pointer isn't wired, end with it as the `Needs you` question, below the `Next:` bullets.
