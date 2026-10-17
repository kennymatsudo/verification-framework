# ADR 0002: Setup proves readiness and resumes from the harness

Status: Accepted. 2026-10-13.

## Problem

Setup can pick the wrong app in a monorepo, or stop on missing startup instructions, a missing checkout, or a personal login. Answers left in chat are gone on the next attempt, and a partial harness must not look ready just because its files exist. Setup is also where a developer first meets the framework, so it has to finish with something they can trust and stop there.

## Decision

setup-verification creates or resumes the harness, builds its doctor (the readiness check) and `check.py`, and proves the environment is ready on the real app. It ends with zero feature checks allowed; building them is add-feature-checks' job ([ADR 0003](0003-each-skill-owns-one-part-of-verification.md)).

- **Find the target first.** Resolve the app from the user's task and the project's wiring before investigating startup. Pick a matching harness by scope, and ask when the evidence leaves a real choice. An unresolved target is a question in the reply, not a saved record.
- **Save progress in the harness.** Create the harness as soon as the target is known: the rules, the scripts, settings marked `incomplete`, and a Setup record in `status.md` with the target, sourced findings, places inspected, blocker, next action, and doctor proof. Resume by reading that record and rechecking its sources.
- **Ready means proven.** Settings become `ready` only once the real doctor has run and `check.py` passes. Incomplete setup stops every other skill with its resume action. A ready record is history; every run still checks the current instance.
- **Never guess a command.** Without a usable environment, ask about an existing one or offer help establishing one; creating one needs the user's direction.
- **Settings hold only what varies by app.** Values that never vary, such as the map check command, the lane definitions, and the exploration ledger's path, live in `rules.md`.

## Options we passed on

- **Keep discovery in chat.** The next attempt repeats the work and loses the blockers.
- **A temporary setup file outside the harness.** A second place to look and a move step, only to cover the minutes before the folder exists.
- **Build an environment automatically.** It expands the request and can change shared systems.
- **Have setup also build feature checks.** Its name doesn't say so, and developers were surprised by the turn into proof building.
- **Keep lanes in settings for app-specific notes.** Setup can't answer it yet, and results already name their lane.

## What changes

setup-verification's steps and `setup.md`, the settings and status templates, `rules.md`'s Setup section, `check.py`'s setup gate, and every skill's entry check.
