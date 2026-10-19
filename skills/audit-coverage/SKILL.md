---
name: audit-coverage
description: >-
  Audit a repo's verification harness for coverage: find requirements and
  features with no check, and checks that no longer match the code or the
  running app. Maps every requirement clause to a check, checks the feature
  map's format, reads each feature's source in parallel, drives every feature
  live, re-runs planned breaks for changed checks, and fixes the harness.
  Use for "audit coverage", "what aren't we checking?", "is the
  feature map current", "does every requirement have a check". Use
  audit-weak-checks to find checks that can't fail, add-feature-checks to
  add coverage, and setup-verification to establish readiness.
disable-model-invocation: true
---

# Audit coverage

You own an honest answer to "does this harness cover the app as it is today?", and the harness fixes that make the answer yes. Cover every feature from source and drive every feature live. Fix the harness; report the product.

## Outcomes

End with exactly one:

- **clean:** every feature covered from source and live, nothing to fix.
- **changed:** harness corrections made and proven, left as one reviewable change.
- **blocked:** coverage could not finish. Say what blocked it.

## 1. Find the harness

Look for `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first. Several: ask which. None: stop and point the user at setup-verification.

Done when you have the harness path and have read its `SKILL.md`, `rules.md`, `settings.md`, `features/README.md`, and `status.md`.

## 2. Run the mechanical check

Run the harness's `scripts/framework/validate.py`. If it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop. Fix every error in the map itself: missing or extra index entries, malformed lines, proof commands whose files moved. Keep each warning about stale or missing evidence for step 6.

Done when `validate.py` exits 0 and you have a list of stale sub-features, or setup stopped with its saved blocker.

## 3. Map the requirements

Read the requirements source named in `settings.md` and the harness's `features/requirements.md`. Skip this step when there is no requirements source, and say so in the reply. A green run proves only the claims someone listed; this traceability pass finds requirements that never became a sub-feature.

Note when the source last changed. If the map records a checked version or date and neither the source nor the feature map changed since then, skip to step 4 and carry the open items into the reply.

Do not turn a pass on one version or a known failure into a claim about intended behavior.

1. Break each requirement into clauses: each state, direction, count, or ordering it names. "Messages arrive in order exactly once" is three clauses. A requirement too vague to break down gets a proposed edit asking its owner for the clauses. Add requirements the design docs state that the source does not.
2. Give each clause the first outcome that fits:
   - A sub-feature proves it: `ids: <IDs>`.
   - The team knows the requirement and the source lacks it: `not in source`, and propose adding it.
   - The source contradicts the code, a design doc, or the agreed scope: add no check; record it under "Conflicts with the source", naming both sides, as an edit its owner can paste.
   - The expected behavior is undecided: `blocked on decision: <the decision>`.
   - None of these: add the sub-feature to its feature file with `No check yet.` and set `No check yet`.
3. Trace backward: a sub-feature no clause, design doc, or scope needs gets a proposed removal or `out of scope: <reason>`.
4. Update the map's checked version or date when it has one.

Hand fact lookups (whether a change is merged, where the code decides a behavior) to subagents on a mid-tier model, each answer carrying its `path:line` or URL, and check that evidence. Split clauses and choose outcomes yourself; a summary that drops a clause is the failure this step exists to catch.

Done when every clause and every sub-feature has exactly one outcome, and `validate.py` exits 0 when the harness's map changed.

## 4. Read the source

Spawn one read-only subagent per feature file, in parallel, on a mid-tier model, with the prompt in `references/reader-prompt.md`. Readers never run the app and never edit.

Done when every feature file has a returned report.

## 5. Reconcile

For each report, spot-check the drift it cites against the code, without re-proving claims it found clean. Collect user-facing surfaces readers found with no feature file; keep only those with a cited source path, and carry each one into triage as a finding. Merge the live recipes into as few app states as practical.

Done when every cited drift is confirmed or dismissed, with the reason.

## 6. Drive every feature live

Follow the harness's own `SKILL.md` to check the instance and drive. Run every sub-feature's proof command at least once, plus the live recipe for any sub-feature marked "No check yet" or "Unreachable". Throughout:

- Run the doctor before the first drive, after any failed drive, and reset or relaunch when the app is wedged in a state the doctor cannot see.
- Confirm evidence files, and the run folders they name, still exist after every cleanup.
- Clean up whatever a failed drive left behind before the next one.
- An "Unreachable" sub-feature stays unreachable only with its blocker and the route tried. If the blocker is gone, it is drift.

For each check whose own code changed since the date on its "Break-tested" line, load add-feature-checks to re-run its planned-break proof, or mark it "Not break-tested".

Done when every sub-feature has a live result: passed, failed, or not run with a reason.

## 7. Triage

Diagnose each failed drive per the harness's Evidence section before sorting it. Sort every finding:

- **Map drift:** the feature file describes the app wrongly. Fix the file.
- **Harness gap:** working behavior the harness cannot drive or read, or a failed screen step with no snapshot to diagnose it from. Fix the tool and re-drive it live. A flake seen twice is a harness gap until its cause is found: add the diagnostic that names the cause before retrying.
- **Product bug:** the app is broken. Record it with the failing step and evidence.

Record results in `status.md` as the harness's Reporting section describes, including its `validate.py --require-evidence` run after the fixes. Remove a known failure only after the relevant check passes on the version where it was tracked.

Done when every finding has a category and every harness fix has been driven live.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Edit only files inside the harness and the tools it owns. Propose changes to sources owned by someone else.

Reply: in the harness's Messages shape. After the outcome, what to do next, grouped by who acts (the requirements owner, a developer, the user) and ordered by risk, linking every issue and pull request with its repo. Then the Details: how many features and sub-features were covered from source and live; requirement clauses with no check, and proposed edits to the source; each fix, by category; each product bug, with its evidence file; and sub-features still not verified, with why.
