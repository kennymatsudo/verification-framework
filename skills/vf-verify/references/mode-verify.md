# Verify a change

Follow this when vf-verify runs in verify mode. The Guardrails in vf-verify's `SKILL.md` apply throughout.

You own the claim that a change works, backed by evidence a reviewer can rerun. The app's harness owns its commands and proof rules.

## 1. Locate the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.

Run `<harness>/scripts/framework/vf.py validate --written-for 3` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. Then read its `settings.md` and these `rules.md` sections: Harness layout, Setup, Code under test, Doctor, Checks, and Reporting, with this skill's `references/messages.md` and `references/verification-plan.md`. Lazy-load the rest: Actions before a recipe that takes an action, Evidence before diagnosing a failed step or cutting a clip, Feature map before editing a feature file. Then read `notes.md` for known failures, misleading passes, and untested cases, and `status.md` for the latest results. Every path below is relative to this app harness, never this skill's directory.

Done when one harness is selected and its rules, settings, and current results have been read, or the run stopped with a named blocker.

## 2. Show what will be proved

With no named change or feature, show what the harness can check instead of guessing: each feature in the feature map, its sub-features in plain words, and each one's latest result from `status.md`. Mark the ones touched by uncommitted edits and commits not on the default branch, in every repo `settings.md` lists. Ask which to run, recommending the touched ones, and run nothing until the user picks; their pick is the scope. Empty feature map: say no checks exist yet and offer the add-checks mode.

Run impact analysis: open the feature map and every touched feature file, trace the changed entry points and shared consumers, and list the sub-feature IDs in the blast radius. Before startup or checks, show the preview and settle acceptance conditions as `references/verification-plan.md` says.

Identify missing or unusable proof for the agreed behaviors. A request to verify a change authorizes building reusable proof within that scope.

Done when the user has picked from the list, or has seen the scope and evidence limits, dependent acceptance decisions are resolved, and each listed ID has an existing recipe or an explicit gap.

## 3. Build missing proof

For each missing proof, show what needs building and its evidence limits. An existing-checks-only request stands for the whole run: a later "go ahead", an approval of your own plan, or an answer to a question about expected behavior does not lift it, and every missing proof stays a reported gap. Otherwise, follow `references/mode-add-checks.md` with this harness, the affected IDs, acceptance sources, agreed plan, and this run's action permissions; it owns construction, independent review, and planned-break proof. Ask before dependent work when acceptance is unresolved, permissions are missing, or building would materially widen scope. A blocked or undecided proof never blocks independent recipes.

After the handoff, reread the changed feature files, settings, and results. After builder cleanup, rerun the doctor and every new or changed recipe on the requested checkout and version before the final verdict; neither a scratch pass nor the builder's run counts. If building stays blocked, keep the gap and next action explicit instead of handing off the same blocker again.

Done when each missing proof has a usable recipe or a named gap, the existing-checks-only restriction is honored, and verification can resume without assuming a scratch result applies.

## 4. Check the instance

If no listed behavior has a runnable proof, skip startup and report the gaps.

`vf.py verify` and `vf.py run` run the Doctor command from settings before each check and stop, running nothing, when it does not report ready. Drive only an instance that reports ready and identifies the running version of every repo the claim depends on.

- Not running: read the Start command, startup notes, and its script before deciding who can start it. Start it only when the harness permits, with `vf.py verify --start`, which waits for the readiness check; a prompt, a person's login or credentials, or an unapproved side effect needs the user.
- Running different code: name the running version and stop.

Done when the instance is ready on the code under test, or the run stopped with the reason and the startup or version correction needed.

## 5. Prove the agreed behaviors

Run the listed IDs through `<harness>/scripts/framework/vf.py verify <ids>`, which runs each one's check under "How to prove it" once through `vf.py run` and prints each ID's status line, following the agreed plan and action permissions. When a listed check drives a screen, run `<harness>/scripts/framework/vf.py clip --check` first, and if clips work here set `VERIFY_KEEP_RECORDING=1` for the run, so a passing run keeps its video and a clip needs no rerun. Confirm its entry points and observations actually support the claim; if not, follow step 3 or report the gap. Never extend a pass to an unsupported claim. A run `vf.py run` refuses doesn't count: fix what its `REFUSED:` lines name and rerun it.

Root-cause a failure before calling it a product bug; a run that never reached the claim is not evidence for it. A product bug is reported with the smallest change that would fix it, as a proposed edit in the report, and the behavior stays Failed: never offer to edit the developer's checkout, and never ask twice for that permission. A scratch fix is only for an inverted proof the add-checks mode plans. Diagnose a failed step in the order the Evidence section gives an agent. If `vf.py clip --check` says this machine cannot make stills, diagnose without them and say so in Details; a missing optional tool never blocks a verdict. For a run that kept a recording, build its replay page with `<harness>/scripts/framework/vf.py replay <evidence file>` for the report.

When a check that drives a screen passed with its video kept, prepare an offer to cut a clip of the changed behavior from that run for the developer to attach to the PR; when clips don't work here, prepare the install line `vf.py clip --check` printed instead. Never install a tool unasked.

Done when every listed ID has a result and evidence, or a reason it was not verified.

## 6. Keep the map true

If the change adds, removes, or alters a user-facing behavior, update its feature file in the same change: the sub-feature line, how a user reaches it, and its proof line. Run `<harness>/scripts/framework/vf.py validate` and fix every error. Unresolved gaps stay Not verified.

Done when the feature map describes the changed behavior and the map check passes, or its blocker is named.

## 7. Record and clean up

Every accepted run has already refreshed `status.md`. For each agreed behavior whose check could not run, or whose pass cannot be trusted, record why with `<harness>/scripts/framework/vf.py not-verified <id> "<reason>"`, as the harness's Reporting section describes, then run `vf.py validate --require-evidence`. Update `notes.md` for any new limit on what a pass means or case nobody could test. Clean up only what this run created, stopping instances it started with the Stop command; name anything still open.

Done when every agreed behavior's line in Latest results matches its outcome, `vf.py validate --require-evidence` passes, evidence remains inspectable, and every process or resource this run created is cleaned up or named as still open.

Reply: in the shape `references/messages.md` gives. Each affected sub-feature as Verified, Failed, or Not verified in the preview's behavior wording; behaviors whose existing checks still pass share one line. When proof was built, one line per new check naming, in a few words each, the breaks it failed on. Each Failed line with a recording links its replay page. The `Details:` line names `status.md` and, when any run kept a recording, the full path to `recordings.html`. When step 5 prepared a clip offer, make it the `Needs you` question. Add nothing else: commands, versions, evidence paths, and cleanup are in `status.md` and `notes.md`.
