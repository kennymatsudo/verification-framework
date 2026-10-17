# Build and prove harness components

Put new code where the harness already keeps that kind of code; a harness without a layout yet starts from the recommended one in `references/harness-code.md`.

For each published command, run its --help, then exercise its documented success and failure paths and check they match its guide entry.

## Feature file

Draft intended behavior from the agreed acceptance sources and trace the current code for its entry points and observations. Name missing implementation or proof routes explicitly. Mark every new ID "No check yet." unless this request also adds its check.

**Proof:** the map check command in `settings.md` passes.

## Probe

Pick the question an agent would otherwise answer with raw SQL or curl. Name the command after the thing it reads (`probe order <id>`), not the table or route.

**Proof:** run it on a real ID (exit 0, show the JSON) and on a made-up ID (exit 1, show the hint). Confirm it follows the Probes rules: read-only, and no app code imported.

## Invariant

Pick a rule a user or operator would call a bug whenever it breaks, whatever led there: one live session per user, a stored message appears once, two systems agree on a record's state. Draft candidates from the design docs, the data model's uniqueness and ownership rules, and the state transitions in the code. Wire the probe that reads the same state to list violations under `problems`.

**Proof:** run the probe on a healthy real record (no violations). Then make a planned break in a scratch worktree, as for a check, and show the violation it reports. Pure judging functions also get unit tests with one passing and one breaking state each.

## Action

Decide with the user whether it needs the approval flag: anything outside this machine, shared, paid, or rate-limited does.

**Proof:** with the user's OK for this run, run it once and read the result back with a probe. Run it without the approval flag and show the refusal.

## Check

Map it to the sub-feature IDs it proves, and wait on a ready signal or a probe rather than a fixed sleep. A check that drives a screen records it as the Evidence rules describe. With the first such check, publish the harness's `scripts/replay.py` and `scripts/clip.py` in the tool guide, noting that clips and stills need the optional tools `clip.py --check` reports.

**Proof, in order:**

1. Run it on the current code. Its evidence file matches the format in `rules.md`. If it passes, continue with a planned break. If it fails, distinguish a product failure from a harness or environment failure. A confirmed product failure stays Failed. A wanted but unshipped behavior keeps its failing check and tracking issue; stop its proof here with `Not break-tested: fails on current code (<issue>).` For an existing defect that can be proven with a small scratch fix, invert the next steps: plan the smallest fix instead of a break, and the check must pass on it. Product implementation in the user's checkout is outside this skill.
2. Plan one break: the smallest edit that makes the behavior wrong while the code still builds, such as skipping the write or returning the old value. Before running `git worktree add`, tell the user `Planned break: <the edit>`, or `Planned fix: <the edit>` for an inverted proof.
3. Add a scratch git worktree for the repo that owns the behavior, make the break as an uncommitted edit there, and run the check against that worktree. Record the worktree's state in evidence with `scripts/code_state.py --checkout <repo>=<worktree>`. It must fail on the step that covers the broken behavior; the evidence names every repo that ran. For a recorded check, confirm the failed step names its snapshot and the replay page opens on it.
4. Remove the worktree.
5. Write `Break-tested <date>: <what was broken>. Evidence: <the break run's evidence file>` on the proof line. For an inverted proof, write `Not break-tested: broken on current code; passes on a planned fix (<the fix>).`

If the running app cannot be pointed at a scratch worktree (one instance per machine, human-only start), report the proof as blocked and write `Not break-tested: <reason>.` A user-operated instance may run scratch code only with their permission.

## Scenario

A scenario is a check that walks several sub-features in one user journey. Build it only when the user asks or when the steps cannot run apart (each depends on state from the last). Give it its own feature file that links to the per-feature files, and prove it like a check, with one planned break per sub-feature it claims.

## Exploration setup

Build this when the explore-bugs skill asks for it or the user asks to set up exploration: at least three invariants, and a probe `problems` list if the harness has none.

**Proof:** each invariant's proof.
