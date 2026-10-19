# ADR 0014: Identify uncommitted code by content

Status: Accepted. 2026-10-18.

## Problem

A commit and a dirty flag cannot distinguish two sets of uncommitted edits. A readiness check comparing those values can accept a process that loaded different edits from the checkout under test.

## Decision

`code_state.py` adds `dirty_hash`: SHA-256 of staged and unstaged binary diffs and untracked file names, modes, and contents. It excludes ignored files and the harness, including its copy in a scratch worktree. A clean checkout records null. Evidence for dirty code requires the fingerprint.

The doctor captures this identity when the process loads its code and compares it with the requested checkout. Reading a fresh fingerprint from disk does not establish loaded code. Check implementation fingerprints remain a separate, unresolved decision.

## Options we passed on

- **Commit and dirty flag only.** Different edits have the same identity.
- **Require a commit before verification.** Prevents verification during ordinary development.
- **Store the patch in evidence.** Duplicates source content and can expose secrets.

## What changes

The evidence code entry, `code_state.py`, validation of cited evidence, doctor and settings guidance, and the usage and internal-format docs. Existing harnesses need the current contract and scripts together; no compatibility format or upgrade workflow is added.
