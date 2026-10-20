# ADR 0021: Check the rules copy

Status: Accepted. 2026-10-19.

## Problem

Every harness copies `rules.md` unchanged so it can be checked for edits, but nothing compares the copy with the framework's. An agent can soften a rule in place and every skill keeps following the softened copy. A harness whose rules and framework scripts come from different framework versions also goes unnoticed.

## Decision

- `rules.md` opens with a `Rules version: <n>` line, raised on every change to the file.
- `validate.py` carries the version and the SHA-256 hash of the `rules.md` it ships with. Before the setup gate, it fails a missing copy, a copy on another version ("copy both unchanged from the same framework version"), and a copy on the same version with another hash ("rules.md was edited"). Line endings are normalized before hashing.
- Every skill already runs `validate.py` first, so no skill gains its own version branch. Under [ADR 0001](0001-one-harness-per-app.md), a harness on another version is brought up to date, not supported as it is.

## Options we passed on

- **Hash only, no version line.** A reader couldn't tell an edited copy from an older one, and the error couldn't say which fix applies.
- **Also record the version in `settings.md`.** It duplicates the line in `rules.md` and must change on every upgrade.
- **A `--rules-hash` flag.** The test prints the new hash, and the flag would ship in every harness for a maintainer-only job.
- **Check only at setup.** An edit made later, during a run, is the case that matters.

## What changes

`rules.md`, `validate.py` and its tests, `docs/internals.md`, USAGE.md, and the contract rule in AGENTS.md. Existing harnesses have no version line and fail until `rules.md` and `scripts/framework/` are recopied.
