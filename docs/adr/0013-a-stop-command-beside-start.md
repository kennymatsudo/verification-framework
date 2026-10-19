# ADR 0013: A Stop command beside Start

Status: Proposed. 2026-10-17. Accept once a practice run restarts its app between checks through Stop and every hidden break reaches a verdict.

## Problem

Settings name how to start the app but not how to stop it. Each harness builds its own launch record so the doctor can tell which code is running, and each start script decides what a leftover record means. Anything outside the run that started the app, such as a teammate, a later session, or a test runner, can only kill the processes, which leaves the record behind. In practice runs the next start then refused ("a launch record already exists"), or the doctor said not ready because the launcher it recorded was gone, so every check stopped without a verdict. A developer after a crash or a reboot hits the same wall.

## Decision

`settings.md` gains a required `Stop` line under Commands: the command that stops what Start started and removes its launch record, or `none` when only a person starts the app. Anyone stopping an instance the harness started uses Stop, never a kill. Start replaces a launch record whose processes have exited, so a stale record never blocks the next start. The doctor's proof covers both: not ready after Stop, and a clean start after the server is killed.

## Options we passed on

- **Let callers delete the launch record.** Every caller would need to know each harness's private layout.
- **Have the doctor ignore a dead launcher.** Fixes one symptom; the start script can still refuse.
- **Make Stop optional.** Callers can't tell "no stop needed" from "never built", so the gap returns silently.

## What changes

The settings template and `check.py` (a required `Stop` label), `rules.md`'s Doctor section and feature-map Baseline line, the doctor's build and proof in setup-verification, cleanup in add-feature-checks and verify-change, and `docs/internals.md`, together. Harnesses built earlier fail `check.py` until they add the line, per [ADR 0001](0001-one-harness-per-app.md).
