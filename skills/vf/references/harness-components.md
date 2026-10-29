# Build and prove harness components

Put new code where the harness already keeps that kind of code; a harness without a layout yet starts from the recommended one in `references/harness-code.md`.

For each published command, run its --help, then exercise its documented success and failure paths and check they match its guide entry.

## Feature file

Draft intended behavior from the agreed acceptance sources and trace the current code for its entry points and observations. Name missing implementation or proof routes explicitly. Give every new ID only its `words`, no `check`, unless this request also adds its check.

**Proof:** `scripts/framework/vf.py validate` passes.

## Check

Map it to the sub-feature IDs it proves, and in a check that proves several, give each step the IDs it judges, as the Checks rules in `rules.md` describe.

Wait on a ready signal or a probe rather than a fixed sleep. Clean up when interrupted with SIGINT, and run the same way in a planned break as in a pass, as the Checks rules say. A check that drives a screen records it as the Evidence rules describe.

With the first such check, publish the harness's `scripts/framework/vf.py replay` and `scripts/framework/vf.py clip` in the tool guide, noting that `VERIFY_KEEP_RECORDING=1` keeps a passing run's video, that `recordings.html` shows every check's latest run with a Watch button where a video was kept, and that clips and stills need the optional tools `vf.py clip --check` reports.

**Proof, in order:**

1. Finish every edit to the harness before this run, since this pass is the one its planned breaks build on. An edit while it runs stops the run, and an edit after it means running it again and replaying any break that ran on the old code. Run it on the current code through `scripts/framework/vf.py run -- <check command>`, which builds its evidence from the events it reports and accepts it only when they follow the Evidence rules in `rules.md` and neither the code on disk nor the harness's own code changed. If it passes, continue with a planned break. If it fails, distinguish a product failure from a harness or environment failure. A confirmed product failure stays Failed. A wanted but unshipped behavior keeps its failing check and tracking issue; stop its proof here with `not_break_tested` set to `fails on current code (<issue>)`. For an existing defect that can be proven with a small scratch fix, invert the next steps: plan the smallest fix instead of a break, and the check must pass on it. Product implementation in the user's checkout is outside this skill.
2. Plan every break for the change before running any: per sub-feature, the smallest edit that makes that behavior wrong while the code still builds, such as skipping the write or returning the old value. A break credits only the behavior whose step fails first, plus any other behavior that same step judges, so plan one break per behavior, aimed past the earlier steps so they still pass. Tell the user all of them in one preview, one line each: `Planned break: <the edit>, caught by <step>, passing through <earlier steps that read its output>`, or `Planned fix: ...` for an inverted proof. The preview informs and asks nothing; only when the breaks have real or shared side effects, ask once for their total, counting each break up to the last step judging a target when a pass of the same harness code exists, since `vf.py run` ends a break's run there, and otherwise through the whole check.
3. Run `scripts/framework/vf.py break start <repo>` once for each repo that owns a planned behavior. It breaks in place in a worktree `vf.py break worktree` made, or copies the code under test into a scratch worktree and points the app at it, and prints which and the path. For each break in that repo in turn, make it there as an uncommitted edit, never in the developer's checkout, then run `vf.py break run <repo> "<sub-feature IDs>: <the edit>" -- python3 scripts/framework/vf.py run -- <check command>`, pointing the check at the copy when it starts the app itself. It must fail on a step that judges each targeted sub-feature, with every earlier failed step judging that same sub-feature; a failure only in steps judging other sub-features, or after any other step failed, proves nothing for it, so plan a break that reaches its own step cleanly; the evidence names every repo that ran. For a recorded check, confirm the failed step names its snapshot and the replay page opens on it.
4. Run `vf.py break end <repo>`, even after a failure, and report anything it says changed in the developer's checkout. Until it ends, `code_state.py` refuses ordinary code recording. A run `break run` held because the copy changed during it never counts; save what changed, end, and run that break again. Then run every check the session credited once more on the restored code, before reporting it.
5. `vf.py break run` prints `Break recorded for <id>: step '<name>' caught it` for each targeted sub-feature whose own step failed and logs it in `evidence/breaks.jsonl`; `vf.py status` now reports the behavior Verified with the break's date. Write nothing about the break in the map, and remove the entry's `not_break_tested` if it had one. For an inverted proof, set `not_break_tested` to `broken on current code; passes on a planned fix (<the fix>)`.

If `start` stops because `harness.json`'s `start` is `user` (only a person can start the app), report the proof as blocked and set the entry's `not_break_tested` to the reason.

## Scenario

A scenario is a check that walks several sub-features in one user journey. Build it only when the user asks or when the steps cannot run apart (each depends on state from the last). Give it its own feature file that links to the per-feature files, and prove it like a check, with one planned break per sub-feature it claims, each aimed at that sub-feature and caught by its own step.
