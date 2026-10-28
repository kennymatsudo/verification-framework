# Coverage mode

Follow this when vf runs in audit mode for coverage. Run it only when the person asked for this job by name in this session; otherwise offer it in one line and stop. The Guardrails in vf's `SKILL.md` apply throughout, and in this mode edit only files inside the harness and the tools it owns; propose changes to sources owned by someone else.

You own an honest answer to "does this harness cover the app as it is today?", and the harness fixes that make the answer yes. Cover every feature from source and drive every feature live. Fix the harness; report the product.

## Outcomes

End with exactly one:

- **clean:** every feature covered from source and live, nothing to fix.
- **changed:** harness corrections made and proven, left as one reviewable change.
- **blocked:** coverage could not finish. Say what blocked it.

## 1. Find the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.

Done when you have the harness path and have read its `SKILL.md`, `rules.md`, `harness.json`, every file in `features/`, `status.md`, and `notes.md`.

## 2. Run the mechanical check

Run `<harness>/scripts/framework/vf.py validate --written-for 8` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. Fix every error in the map itself: malformed entries, check commands whose files moved. Keep each warning about stale or missing evidence for step 5.

Done when `vf.py validate` exits 0 and you have a list of stale sub-features, or setup stopped with its saved blocker.

## 3. Read the source

Spawn one read-only subagent per feature file, in parallel, on a mid-tier model, with the prompt in `references/reader-prompt.md`. Give each reader the commit range from its sub-features' oldest last pass to HEAD in every repo, from step 2's warnings, or say no pass is recorded, so it opens from what merged since the harness last saw this feature. Readers never run the app and never edit.

Done when every feature file has a returned report.

## 4. Reconcile

For each report, spot-check the drift it cites against the code, without re-proving claims it found clean. Collect user-facing surfaces readers found with no feature file; keep only those with a cited source path, and carry each one into triage as a finding. Merge the live recipes into as few app states as practical.

Done when every cited drift is confirmed or dismissed, with the reason.

## 5. Drive every feature live

Follow the harness's own `SKILL.md` to check the instance and drive. Run every checked sub-feature through `scripts/framework/vf.py verify <ids>`, which runs the readiness check before each check and stops when the app is not ready, plus the live recipe for any behavior with no `check` or with an `unreachable` block. Throughout:

- Rerun the doctor after any failed drive, and reset or relaunch when the app is wedged in a state the doctor cannot see.
- Confirm evidence files, and the run folders they name, still exist after every cleanup.
- Clean up whatever a failed drive left behind before the next one.
- A behavior with an `unreachable` block stays unreachable only with its blocker and the route tried. If the blocker is gone, it is drift.

For each behavior `status.md` reports as `Pass not proven: <file> changed since this run`, rerun its check. For each one it reports as `Pass not proven: <file> changed since its planned break`, follow `references/mode-add-checks.md` to replay its planned break.

Done when every sub-feature has a live result: passed, failed, or not run with a reason.

## 6. Triage

Diagnose each failed drive per the harness's Evidence section before sorting it. Sort every finding:

- **Map drift:** the feature file describes the app wrongly. Fix the file.
- **Harness gap:** working behavior the harness cannot drive or read, or a failed screen step with no snapshot to diagnose it from. Fix the tool and re-drive it live. A flake seen twice is a harness gap until its cause is found: add the diagnostic that names the cause before retrying.
- **Product bug:** the app is broken. Record it with the failing step and evidence.

Every accepted run has already refreshed `status.md`; record a behavior that could not be driven with `vf.py not-verified`, as the harness's Reporting section describes, and run `vf.py validate --require-evidence` after the fixes. Remove a known failure from `notes.md` only after the relevant check passes on the version where it was tracked.

Done when every finding has a category and every harness fix has been driven live.

## Reply

In the shape `references/messages.md` gives. After the outcome, what to do next, grouped by who acts (the requirements owner, a developer, the user) and ordered by risk, linking every issue and pull request with its repo. Then each product bug in one line, and the sub-features still not verified, grouped by reason. How much was covered from source and live, each fix by category, and the evidence files stay in `status.md` and the change left for review.
