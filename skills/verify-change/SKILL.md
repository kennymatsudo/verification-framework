---
name: verify-change
description: >-
  Verify a change using an existing app verification harness and record evidence
  from the running app. Use when a verify-<app> skill delegates here, or for
  "verify this change" and "check checkout on this branch" with an existing
  harness. Use setup-verification to create a harness and add-feature-checks
  to add a missing check.
---

# Verify a change

You own the claim that a change works, backed by evidence a reviewer can rerun. The app's harness owns its commands and proof rules.

## 1. Locate the harness

Use the harness directory supplied by the app skill or the user; otherwise glob `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`). Several matches: ask which. None: stop and name setup-verification.

Read its `settings.md` and these `rules.md` sections: Harness layout, Verification plan, Setup, Code under test, Lanes, Doctor, Checks, Messages, and Reporting. Lazy-load the rest: Actions before a recipe that takes an action, Evidence before diagnosing a failed step or cutting a clip, Feature map before editing a feature file. Then read `status.md` for known failures, misleading passes, and untested cases. Run `<harness>/scripts/framework/validate.py` before startup; if it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop. Every path below is relative to this app harness, never this skill's directory.

Copy the harness directory to a temporary folder outside it, leaving out `evidence/`, `recordings.html`, and `__pycache__` folders, which runs rewrite. A copy works whether or not the harness is tracked by Git, and step 5 compares against it.

Done when one harness is selected, its rules, settings, and current results have been read, and its copy is taken, or the run stopped with a named blocker.

## 2. Show what will be proved

With no named change or feature, show what the harness can check instead of guessing: each feature in the feature map, its sub-features in plain words, and each one's latest result from `status.md`. Mark the ones touched by uncommitted edits and commits not on the default branch, in every repo `settings.md` lists. Ask which to run, recommending the touched ones, and run nothing until the user picks; their pick is the scope. Empty feature map: say no checks exist yet and name add-feature-checks.

Run impact analysis: open the feature map and every touched feature file, trace the changed entry points and shared consumers, and list the sub-feature IDs in the blast radius. Before startup or checks, show the preview and settle acceptance conditions per the harness's Verification plan rules.

Identify missing or unusable proof for the agreed behaviors. A request to verify a change authorizes building reusable proof within that scope.

Done when the user has picked from the list, or has seen the scope and evidence limits, dependent acceptance decisions are resolved, and each listed ID has an existing recipe or an explicit gap.

## 3. Build missing proof

For each missing proof, show what needs building and its evidence limits. Unless the request is existing-checks-only, load add-feature-checks by name with this harness, the affected IDs, acceptance sources, agreed plan, and this run's action permissions; it owns construction, independent review, and planned-break proof. Ask before dependent work when acceptance is unresolved, permissions are missing, or building would materially widen scope. If add-feature-checks is unavailable, report the installation dependency and keep that behavior Not verified. A blocked or undecided proof never blocks independent recipes.

After the handoff, reread the changed feature files, settings, and results, and replace the step 1 copy with a fresh one, since the handoff's edits are expected. After builder cleanup, rerun the doctor and every new or changed recipe on the requested checkout and version before the final verdict; neither a scratch pass nor the builder's run counts. If building stays blocked, keep the gap and next action explicit instead of handing off the same blocker again.

Done when each missing proof has a usable recipe or a named gap, the existing-checks-only restriction is honored, and verification can resume without assuming a scratch result applies.

## 4. Check the instance

If no listed behavior has a runnable proof, skip startup and report the gaps.

Run the Doctor command from settings. Drive only an instance that reports ready and identifies the running version of every repo the claim depends on.

- Not running: read the Start command, startup notes, and its script before deciding who can start it. Start it only when the harness permits; a prompt, a person's login or credentials, or an unapproved side effect needs the user. Wait for the Ready line and rerun the doctor before driving it.
- Running different code: name the running version and stop.

Done when the instance is ready on the code under test, or the run stopped with the reason and the startup or version correction needed.

## 5. Prove the agreed behaviors

Run each listed ID's recipe under "How to prove it", following the agreed plan, the harness's lanes, and action permissions. Confirm its entry points and observations actually support the claim; if not, follow step 3 or report the gap. Never extend a pass to an unsupported claim.

Root-cause a failure before calling it a product bug; a run that never reached the claim is not evidence for it. Diagnose a failed step in the order the Evidence section gives an agent. If `clip.py --check` says this machine cannot make stills, diagnose without them and say so in Details; a missing optional tool never blocks a verdict. For a run that kept a recording, build its replay page with `<harness>/scripts/framework/replay.py <evidence file>` for the report.

When a check that drives a screen passed, run `<harness>/scripts/framework/clip.py --check`. If clips work here, prepare an offer to rerun it with `VERIFY_KEEP_RECORDING=1` and cut a clip of the changed behavior for the developer to attach to the PR; otherwise prepare the install line it printed. Never install a tool unasked.

After the last check, diff the harness against the copy, with the same folders left out. Any difference is an edit made outside the add-feature-checks handoff: handle it as the harness's Reporting section says.

Done when every listed ID has a result and evidence, or a reason it was not verified, and the harness diff is empty or its edits are handled.

## 6. Keep the map true

If the change adds, removes, or alters a user-facing behavior, update its feature file in the same change: the sub-feature line, how a user reaches it, and its proof line. Run `<harness>/scripts/framework/validate.py` and fix every error. Unresolved gaps stay Not verified.

Done when the feature map describes the changed behavior and the map check passes, or its blocker is named.

## 7. Record and clean up

Record results in `status.md` as the harness's Reporting section describes, including its `validate.py --require-evidence` run. Clean up only what this run created, stopping instances it started with the Stop command, and remove the harness copy; name anything still open.

Done when the results are recorded and pass `validate.py --require-evidence`, evidence remains inspectable, and every process or resource this run created is cleaned up or named as still open.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.

Reply: in the harness's Messages shape. When step 5 found harness edits, open with the `Harness edited during this run` line. Then each affected sub-feature as Verified, Failed, or Not verified in the preview's behavior wording; behaviors whose existing checks still pass share one line. When proof was built, one line per new check naming, in a few words each, the breaks it failed on. Each Failed line with a recording links its replay page. When any run kept a recording, add one line: `Recordings: <full path to recordings.html>`. When step 5 prepared a clip offer, make it the `Needs you` question. Add nothing else: commands, versions, evidence paths, and cleanup belong in `status.md`.
