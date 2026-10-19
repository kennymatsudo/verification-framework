# ADR 0016: Anchor a harness on its project root

Status: Accepted. 2026-10-19.

## Problem

The framework treated the Git top level as the app. When the app is one folder of a larger repository, that breaks three ways. Recipe commands had to be written and run from the top of the whole repository, so every path carried the app's folder name. The harness's own repo entry, `.`, covered the whole repository, so any edit in an unrelated project marked every run's code as dirty. And skills looked for a harness only in the top folder's skills directories, so they missed a harness in the app's own folder.

## Decision

The project root is the folder holding the skills directory the harness sits in: `app/` for `app/.agents/skills/verify-app/`. In a single-repo app it is the Git top level, so nothing changes there.

- Recipe commands run from the project root, and `validate.py` checks their paths from it.
- `settings.md` repo locators and `env:` files resolve from it. A locator that names a folder inside a checkout scopes `dirty` and `dirty_hash` to that folder; `commit`, `branch`, and `on_main` stay the checkout's.
- Skills and `locate.py` find a harness in the skills directories of the current folder and each folder above it up to the Git top level, nearest first.

The harness's location already says which project it belongs to, so this adds no setting.

## Options we passed on

- **A `Project root:` line in settings.** A second way to say what the harness's location already says, and one that can disagree with it.
- **Keep the Git top level and write long paths.** Leaves every monorepo app dirty on unrelated edits and its harness unfindable.
- **A per-repo list of folders to watch for dirty state.** More settings for a case the locator's own folder already covers.

## What changes

`rules.md` (project root, recipe paths, dirty scope); the `settings.md` template; `validate.py`, `code_state.py`, and explain-harness's `trust_facts.py` resolve from the project root, and dirty state excludes the harness with a path from the repository's top; `locate.py` and every skill's harness search walk up from the current folder; USAGE.md, `docs/internals.md`, `docs/architecture.md`, and AGENTS.md. Existing single-repo harnesses need no change. A monorepo harness rewrites its recipe paths and repo locators from its project root and recopies `scripts/framework/`.
