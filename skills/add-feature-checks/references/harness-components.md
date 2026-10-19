# Build and prove harness components

Put new code where the harness already keeps that kind of code; a harness without a layout yet starts from the recommended one in `references/harness-code.md`.

For each published command, run its --help, then exercise its documented success and failure paths and check they match its guide entry.

## Feature file

Draft intended behavior from the agreed acceptance sources and trace the current code for its entry points and observations. Name missing implementation or proof routes explicitly. Mark every new ID "No check yet." unless this request also adds its check.

**Proof:** the map check command in `settings.md` passes.

## Invariant

Pick a rule a user or operator would call a bug whenever it breaks, whatever led there: one live session per user, a stored message appears once, two systems agree on a record's state. Draft candidates from the design docs, the data model's uniqueness and ownership rules, and the state transitions in the code. Wire the probe that reads the same state to list violations under `problems`, loading add-tools to build that probe when none exists.

**Proof:** run the probe on a healthy real record (no violations). Then make a planned break in a scratch worktree, as for a check, and show the violation it reports.

## Check

Map it to the sub-feature IDs it proves, and in a check that proves several, give each step the IDs it judges, as the Checks rules in `rules.md` describe.

Wait on a ready signal or a probe rather than a fixed sleep. A check that drives a screen records it as the Evidence rules describe.

With the first such check, publish the harness's `scripts/framework/replay.py` and `scripts/framework/clip.py` in the tool guide, noting that `VERIFY_KEEP_RECORDING=1` keeps a passing run's video, that `recordings.html` shows every check's latest run with a Watch button where a video was kept, and that clips and stills need the optional tools `clip.py --check` reports.

**Proof, in order:**

1. Run it on the current code. Its evidence file matches the format in `rules.md`. If it passes, continue with a planned break. If it fails, distinguish a product failure from a harness or environment failure. A confirmed product failure stays Failed. A wanted but unshipped behavior keeps its failing check and tracking issue; stop its proof here with `Not break-tested: fails on current code (<issue>).` For an existing defect that can be proven with a small scratch fix, invert the next steps: plan the smallest fix instead of a break, and the check must pass on it. Product implementation in the user's checkout is outside this skill.
2. Plan one break for one sub-feature: the smallest edit that makes that behavior wrong while the code still builds, such as skipping the write or returning the old value. Before starting a session, tell the user `Planned break: <the edit>`, or `Planned fix: <the edit>` for an inverted proof.
3. Run `scripts/framework/break_session.py start <repo>` for the repo that owns the behavior. It copies the code under test into a scratch worktree, points the app at it, and prints its path. Make the break or fix there as an uncommitted edit, never in the developer's checkout. Then run `break_session.py run <repo> "<sub-feature ID>: <the edit>" -- <check command>`, pointing the check at the scratch copy when it starts the app itself. It must fail on a step that judges the broken sub-feature; a failure only in steps judging other sub-features proves nothing for it, so plan a break that reaches its own step; the evidence names every repo that ran. For a recorded check, confirm the failed step names its snapshot and the replay page opens on it.
4. Run `break_session.py end <repo>`, even after a failure, and report anything it says changed in the developer's checkout. Until it ends, `code_state.py` refuses ordinary code recording.
5. Write `Break-tested <date>: <what was broken>. Evidence: <the break run's evidence file>` on the broken sub-feature's proof line, and on no other. For an inverted proof, write `Not break-tested: broken on current code; passes on a planned fix (<the fix>).`

If `start` stops because `Run scratch code` is `none`, report the proof as blocked and write `Not break-tested: <reason>.` A user-operated instance may run scratch code only with their permission.

## Scenario

A scenario is a check that walks several sub-features in one user journey. Build it only when the user asks or when the steps cannot run apart (each depends on state from the last). Give it its own feature file that links to the per-feature files, and prove it like a check, with one planned break per sub-feature it claims, each aimed at that sub-feature and caught by its own step.

## Exploration setup

Build this when the explore-bugs skill asks for it or the user asks to set up exploration: at least three invariants, and a probe `problems` list if the harness has none.

**Proof:** each invariant's proof.
