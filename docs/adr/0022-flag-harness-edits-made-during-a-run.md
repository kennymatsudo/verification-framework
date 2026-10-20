# ADR 0022: Flag harness edits made during a run

Status: Accepted. 2026-10-19.

## Problem

An agent facing a failing check can loosen the check instead of fixing the code. The guardrails forbid it, but instructions alone barely help, and models attempt it most when a task can't be finished honestly, which includes a check failing on a real bug. Nothing in a run records whether the harness changed between its first and last check.

## Decision

verify-change copies the harness when a run starts and compares it after the last check.

- In step 1 it copies the harness directory, leaving out `evidence/`, `recordings.html`, and `__pycache__` folders, which runs rewrite, to a temporary folder. A copy works whether or not the harness is tracked by Git, and yields the diff a hash can't.
- An add-feature-checks handoff is expected to change the harness, so verify-change takes a fresh copy when the handoff returns.
- If anything differs after the last check, before the run's own feature-file edits, the report opens with `Harness edited during this run: <files>` before any verdict, and the diff goes in `status.md`. Every sub-feature whose check or read changed is Not verified until add-feature-checks proves it again with a planned break.

The flag is silent when nothing changed.

## Options we passed on

- **Rely on the guardrail.** Checking works where telling doesn't.
- **Make the harness read-only during a run.** Blocks the add-feature-checks handoff, and a sandbox can't be assumed in every agent.
- **Replay planned breaks on every run.** Costs a scratch worktree per check per run; the flag shows whether that cost is ever needed.

## What changes

verify-change steps 1, 3, 5, and 7 and its Reply line, `rules.md` Reporting, and USAGE.md's Verify a change. add-feature-checks is unchanged: its edits are the ones a run expects.
