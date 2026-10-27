# ADR 0012: Vendor only what bears trust

Status: Accepted. 2026-10-27. Second step of [the redesign](../redesign-proposal.md).

## Problem

Every harness carried twelve framework scripts, 5,633 lines, in its `scripts/framework/`. Three of them, the weak-checks audit's `break_checks.py`, `smells.py`, and `weakened.py` (551 lines), judge a harness's own test code rather than a run: they decide nothing about a verdict, they only work on Python check code, and the audit mode already does their job by hand for other languages. They were copied into every harness only so a vf copy committed beside the harness could run them, since a committed skill carries no `scripts/` ([ADR 0007](0007-the-framework-ships-inside-the-app-repo.md)). Each copy is one more vendored file for a reviewer to skip, one more hash in `framework.sha256`, and one more thing an update rewrites.

## Decision

A harness carries the scripts that record runs, run planned breaks, compute verdicts, launch the app, find the harness, gather trust facts, and show recordings: `vf.py`, `validate.py`, `code_state.py`, `break_session.py`, `launch.py`, `locate.py`, `trust_facts.py`, `replay.py`, and `clip.py`. The three audit scripts stay in the installed vf's `scripts/` and are not copied. `sync` removes them from a harness that has them, as it removes any file an earlier sync recorded that the framework no longer ships.

- **The viewer stays vendored.** `replay.py` and `clip.py` decide no verdict either, but they are how a teammate who never installed the framework opens a failed run's recording and cuts a clip for a pull request; dropping them would take that from the person ADR 0007 exists for.
- **This partly reverses ADR 0007.** A teammate running the weak-checks audit from the committed vf copy no longer has the scripted sweep; the mode tells them to do the same steps by hand, as it already does for non-Python harnesses, and to say so in the readout. The owner, who installs the framework, keeps the scripts.
- **Two scripts wait for later steps.** `locate.py` is what the committed vf copy runs to find the harness and its sibling skills; it leaves when the three skills become one. `trust_facts.py` folds into `vf.py status --json` once the manifest replaces the proof-line parsing it duplicates.
- The Rules version does not rise: nothing a harness must do changes, and `validate.py` never looked for these files.

## Options we passed on

- **Concatenate the vendored scripts into one file.** `framework.sha256` already hashes a list, and the "predates the framework" check keys on a missing subcommand, so one file buys little and makes the copy harder to read.
- **Drop the viewer too.** Saves 1,594 lines per harness and costs the non-installing teammate recordings and clips.
- **Drop `locate.py` and `trust_facts.py` now.** Both need a skill rewrite that the one-skill and manifest steps make moot.
- **Keep the audit scripts and make them optional.** A branch in the audit mode for a file that may or may not be there, to keep code no run depends on.

## What changes

`vf.py` (`FRAMEWORK_SCRIPTS`), vf's `references/mode-audit-weak-checks.md`, `docs/internals.md`, `docs/architecture.md`, and `tests/test_vf.py`. A harness updated with `sync` loses three files and three lines of `framework.sha256`.
