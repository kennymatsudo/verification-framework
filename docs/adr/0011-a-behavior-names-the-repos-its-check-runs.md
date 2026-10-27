# ADR 0011: A behavior names the repos its check runs

Status: Accepted. 2026-10-27. Completes the first step of [the redesign](../redesign-proposal.md) that [ADR 0010](0010-start-takes-the-checkout.md) began.

## Problem

Every run recorded every repo in `settings.md`, and a run stopped when any one of them was missing from the machine. For an app spread over several repos that is right for a check that drives all of them and wrong for one that never touches a repo: in the first converted app, a teammate without the frontend checkout could not run even the backend-only checks. Requiring every repo also made the Verified line claim more than the check had exercised.

## Decision

A behavior's proof line may name the repos its check runs: `` `<command>`. Reads the order row (state). Repos: api. `` Each name must be a repo under `## Repos`. A line that names none runs every repo, which is what every harness did before, so nothing existing changes.

- **A run records the repos its behaviors need.** `vf.py run` looks up the behaviors the map proves with its exact command and records the union of their repos; with no such behavior, or one whose line names no repos, it records every repo. A repo outside that set may be absent from the machine. One inside it that is missing, or whose running version cannot be read, still stops the run.
- **A record must cover what it claims.** `vf.py run` refuses a record that claims a behavior whose proof line names a repo the record did not record.
- **Verified needs the behavior's repos, no more.** Both the pass and its planned break record every repo the proof line names. A planned break whose `repo` is not one of them proves nothing for that behavior, since it cannot have changed the code the check ran.
- **`VERIFY_CHECKOUT_<REPO>` follows the same set,** and `vf.py verify --start` fills `Start` with the checkouts this machine has, so a missing repo that `Start` does not name is no obstacle.
- The Rules version rises to 5.

Limit: the framework's launcher (`vf.py start`) still records every repo at start, so a harness that must run without one repo needs a doctor that does not require it.

## Options we passed on

- **The check reports its repos in the `check` event.** Self-reported by the thing under review; a repo left off the list keeps a Verified it should lose.
- **A `Repos` section per feature file.** A second grammar for one fact, and a check in a journey file can run fewer repos than its neighbours.
- **Mark a settings repo as optional.** Says which repo may be absent, not which check needs it, so a Verified line still could not name what ran.
- **Wait for the manifest.** The clause lives on the proof line the manifest step migrates anyway, and the contract hardens on publish, so the change is cheapest now.

## What changes

`rules.md` (Feature map, Code under test, Evidence, Reporting; version 5), `validate.py` (`proof_repos`, `behavior_repos`, `check_proof_repos`, the verdict engine's required set, the break-repo rule), `code_state.py` (`recorded_checkouts` with `only` and `missing`), `vf.py` (`needed_repos`, `uncovered_repo_problems`, the start and verify paths), `break_session.py` (a session tolerates a repo the machine lacks), `docs/internals.md`, the gate version in every skill, and `tests/test_validate.py` and `tests/test_vf.py`.
