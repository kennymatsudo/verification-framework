# ADR 0004: Drive through the app, judge from outside it, and compute every verdict from the evidence

Status: Accepted. 2026-10-21.

## Problem

If harness tools reuse the project's clients, a check can read state through the app's own models and logic, and the product grades itself: a bug that makes the `Order` model report `pending` as `paid` passes the check. Models also overstate proof far more often than they cheat on a check, so an agent-written "Verified" was the likeliest way a harness would mislead; in a pilot an agent reported Verified after changing a check its break had tested. A commit and a dirty flag can't tell two sets of uncommitted edits apart, so a doctor comparing them could accept a process that loaded different code. And each harness's own Git logic drifted: three practice runs produced three versions, one of which hardcoded `main` as the default branch.

## Decision

- **Real entry points, outside reads.** Actions go through the entry point a user or operator uses. The read that decides a verdict (a database row, the rendered screen, a raw HTTP response, a sent message) uses only the project's language, third-party drivers, and connection settings, never the app's models, serializers, or logic. A direct read that breaks on a schema change is a clear failure; a read through app code risks a silent wrong pass.
- **Published tools.** Probes and actions are ordinary repo-local CLI tools in the project's language, with `--help`, enforced permissions, and one entry each in `tools.md` naming at least Permissions and Limits. The guide is linked from the project's agent instructions only with permission. A probe's observation alone is never a verdict.
- **A known version.** Every result records each repo's commit, branch, dirty state, and `dirty_hash`, the SHA-256 of uncommitted diffs and untracked files, from one framework script, `code_state.py`, never from Git directly. The doctor reports the version the running process loaded, not the checkout's HEAD. A pass is evidence only for the recorded versions.
- **Nobody writes a verdict.** `vf.py status` computes each behavior's line in `status.md` from the feature map, the accepted evidence, and the Not verified records: Verified only when the latest accepted run passed on a ready doctor and a planned break backs it; Failed when the latest run failed; otherwise Not verified with the reason. `validate.py` fails a Verified line it would not write now. An agent can lower a result with `vf.py not-verified <id> "<reason>"`, never raise one. Failed and Not verified are never errors: a result can always be understated.
- **Evidence a person can inspect.** Each run is one JSON record beside a folder with its video, snapshots, and logs, with a timeline so a person can watch what the user would have seen and an agent can read stills and page text. A check that drives a screen keeps its video when it fails or when `VERIFY_KEEP_RECORDING=1`.

## Options we passed on

- **Reuse app clients and flag checks that import changed code.** Misses an existing bug in the code the check reads through.
- **Require MCP, or one language for tools.** Adds infrastructure and duplicates the project's clients.
- **Detect app imports in `validate.py`.** It can't read imports reliably in every language; the check review covers it.
- **Keep agent-written result lines and validate them.** Every skill repeats the recording step, and each new field needs a new grammar and rule.
- **Verdicts from evidence alone, with no agent record.** Loses "Not verified: the sandbox account expired".
- **Require a commit before verification, or store the patch in evidence.** Blocks ordinary development; duplicates source and can expose secrets.
- **Store each repo's default branch in settings.** The clone answers it; revisit if `null` shows up often.

## What changes

`rules.md` (Tool discovery, Code under test, Doctor, Probes, Actions, Checks, Evidence, Reporting), `code_state.py`, `validate.py`'s verdict engine and tool guide checks, the add-tools mode, `vf.py status` and `not-verified`, the weak-checks rubric, vf-explain, USAGE.md, and internals.md.
