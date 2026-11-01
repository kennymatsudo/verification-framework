# ADR 0016: Batch independent breaks in one run, and keep a stable scratch worktree

Status: Proposed. 2026-11-01.

## Problem

Planned breaks are the slowest part of verification on a real app, and two costs drive it.

One is the restart. Under [ADR 0015](0015-break-in-the-runs-own-copy-and-credit-only-a-clean-catch.md) a break happens in place in a worktree the framework made, so a pull-request run restarts the app once per break. But add-checks and verify, run from the developer's own checkout, have no such worktree: every session makes a fresh scratch worktree in a temp folder and throws it away at the end. On an app that does not hot reload, that fresh worktree has no build artifacts, so the restart rebuilds everything. The rebuild, not the restart, is the cost, and it is paid again every session.

The other is one break, one run. Clean-catch credits a behavior only when its own step failed and no unrelated step failed before it. A journey check that covers thirty-eight behaviors therefore needs thirty-eight runs to break-test them all, each a full restart. On a slow or quota-limited app that is days of waiting.

Speeding up the second cost ran straight into the clean-catch guarantee. If two breaks are applied at once and the journey fails step A (for behavior A) then step B (for behavior B), clean-catch sees an unrelated failed step (A) before B's step and credits B nothing. So the naive batch proves only the first behavior. Relaxing the rule to credit B anyway would reinstate exactly what ADR 0015 rejected: a knock-on failure, a payment step that failed only because its order was skipped, earning credit it did not deserve.

## Decision

- **A break credits a behavior when every earlier failed step judges that behavior or another of the run's breaks' targets.** This is clean-catch, widened by one clause. For a run that carries a single break it is unchanged, so ADR 0015's guarantee stands exactly: within one break, a step that failed only because an earlier step did still proves nothing, even when the break names both behaviors. The clause only changes runs that carry several breaks: a failed step that judges a *different* break's target counts as that break's own catch, not a knock-on, so it does not spoil this break's behavior. `break_catch` reads the run's breaks and applies this itself; no caller changed.
- **One run may carry several breaks.** `VERIFY_PLANNED_BREAK` and the `vf.py break run` argument take one or more `IDS: what` breaks joined by ` ;; `, and the evidence records `planned_break` as a non-empty list of `{what, sub_features, repo}`. No sub-feature may be named by two of a run's breaks, so a credit always names the break that caught it. The agent makes every break as one edit in the copy, names them all in one `break run`, and `vf.py run` ends the run once every target has failed a step judging it.
- **Breaks in one run must break unrelated code.** The widened clause is sound only when each break's failure is its own. Two breaks that touch shared state can fail a step for the wrong reason, and the evidence cannot tell that from a true catch. The add-checks mode plans batched breaks in unrelated parts of the code, the blind reviewer checks that, and the eval suite's `add-checks` cases, whose hidden breaks must all be caught, guard it. A knock-on that earns no credit is still reported, so interference shows up as a break that proved nothing rather than a silent false pass.
- **The scratch worktree is kept between sessions.** `vf.py break start` uses a stable per-repo worktree instead of a throwaway one: it makes it when absent and reuses the one the last session left when present, so the app's build artifacts survive and a restart does an incremental build. `break end` leaves the worktree at the repo's clean commit for the next session. This needs no contract change; a single break on a kept worktree proves exactly what it did before.
- **The Rules version rises to 9.** A harness on older framework scripts writes the old single-break `planned_break` object; the new `validate.py` does not read it, so the version guards the two apart and `sync` refuses a downgrade.

## Options we passed on

- **Keep clean-catch strict and batch only the restart.** With one edit per break on a non-reloading app, each edit still needs its own restart, so batching the restart alone saves nothing. The restart count only drops when several breaks share one applied state.
- **Credit any target whose earlier failed steps judge some target, within one break too.** This is ADR 0015's rejected option: naming a setup behavior as a target lets a payment step with no order earn credit. The widened clause is confined to *other* breaks, so one break keeps the strict rule.
- **Detect interference automatically.** Nothing in the evidence distinguishes a step that failed from its own break from one that failed from another break's spillover. Independence is a property of the code the breaks touch, which the agent and reviewer judge, not the framework.
- **A persistent marked worktree for add-checks, as in a pull-request run.** In place needs committed code with no uncommitted product changes; add-checks breaks the developer's working tree, uncommitted work included, so it needs a scratch copy. Keeping that scratch copy is the reachable win.
- **A knob to turn batching off, or a temp path to relocate the kept worktree.** One more thing to learn and forget. A single break is already the common case and behaves identically, and the kept worktree lives in the system temp folder, bounded at one per repo.

## What changes

`vf.py` (`parse_planned_break` returns a list, `run_check` takes the union of targets), `validate.py` (`break_entries`, `break_entry_for`, `planned_break_problems`, the widened `break_catch`, `aimed_breaks`, the Verified line), `break_session.py` (a kept scratch worktree in `start`/`end`, a multi-break argument, `record_breaks` and `replay` over the list), `trust_facts.py`; `rules.md` (Checks, Break-tested, Evidence, Reporting, Rules version 9) and every mode's `--written-for`; the add-checks and verify-pr modes and `harness-components.md`; USAGE.md, `docs/internals.md`, `docs/architecture.md`, and `docs/design.md`.
