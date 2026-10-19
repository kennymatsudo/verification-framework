# ADR 0015: A harness layout people can browse

Status: Accepted. 2026-10-18.

## Problem

A harness's folder names were chosen for agents. People opening one met three problems. `scripts/` mixed the framework's four never-edited copies with the app's own tools, and `check.py`, which validates the harness, sat beside the app's checks with nearly the same name. `evidence/` was one flat folder holding every run's record and folder, doctor output, and the exploration ledger, named with compact timestamps like `20261014T171718Z`, so it became an unreadable pile within days. And nothing in the folder told a person where to start or where recordings were.

## Decision

- The framework's copies live in `scripts/framework/`, so "never edit" shows in the path and an upgrade replaces one folder. `check.py` becomes `validate.py`, so "check" only means a feature check.
- Each check's runs live in `evidence/<check>/`, as `<time>.json` beside a `<time>/` folder; doctor output goes in `evidence/doctor/`. Times in file names are UTC with dashes, such as `2026-10-03T14-02-11Z`. `validate.py` rejects a cited run outside a check folder.
- The recordings page is `recordings.html` at the harness's top level, created at setup.
- Every harness has a `README.md`, written by setup, that tells a person what the folder is and links results, recordings, the feature map, and tools. `validate.py` requires it.

## Options we passed on

- **Keep the flat layout and rely on the recordings page.** Fixes finding videos, not browsing evidence, reviewing it in a pull request, or telling framework files from app files.
- **Rename only, no `scripts/framework/`.** Leaves never-edited files mixed with edited ones.
- **Group evidence by date.** People look for a behavior, not a day; the recordings page already sorts by time.
- **Readable run folder names, such as the branch.** Branches contain slashes and change; the record already holds the branch.

## What changes

`rules.md`'s layout and evidence naming; `validate.py` (renamed, per-check evidence, required README); `code_state.py`, `replay.py`, `clip.py`, and explain-harness's `trust_facts.py` for the new paths; a README template and setup's copy step; every skill's script paths; USAGE.md, `docs/internals.md`, and AGENTS.md. Existing harnesses need rebuilding into the new layout; no compatibility or migration is added.
