# ADR 0011: Put each format where its readers look, including a recommended code layout

Status: Proposed. 2026-10-14. Accept once a TypeScript harness has been built with the code layout and it fit without forcing, and a build run in a fresh session never loads setup-verification.

## Problem

`rules.md` says what harness code must do (print each check as it runs, share reads between probes and checks, write evidence before cleanup) but not how to lay it out, so each agent invents its own structure. One harness built over many runs arrived at a layout that makes those rules easy to follow, and a new harness starts without those lessons. Separately, add-feature-checks loaded all of setup-verification to read three formats, putting steps the builder must not follow into its context, while verify-change and audit-coverage edited the feature map without ever reading its format.

## Decision

Move each format to where the skills that use it already read.

- **Feature map format** is a section in `rules.md`. `check.py` enforces it, so it's part of the contract, and every skill that edits the map already reads `rules.md`. Skills that read only named sections read this one before editing the map.
- **Code layout** lives in add-feature-checks' `references/harness-code.md`, since it builds every tool after the doctor. It is a recommendation in language-neutral terms: connections, reads, invariants, actions, a run recorder, and commands, each with one job. Setup's `doctor.md` states the one rule the doctor needs from it: keep connection setup in its own module so later tools reuse it. A harness or project with its own layout keeps it. Nothing outside the building agent reads the layout, so it stays out of `rules.md`, `check.py` doesn't check it, and it has no structure tests.
- **Tool guide template** stays with setup, which writes the first entry. add-feature-checks adds entries in the shape of the existing ones, with every field the Tool discovery rules list.

add-feature-checks no longer loads setup-verification.

## Options we passed on

- **No example layout.** Every harness relearns the same lessons.
- **Require the layout, with structure tests.** Work and review for something no reader of a harness uses, and it fights projects that already organize this code.
- **Ship a Python module harnesses copy.** Helps only Python projects, and every harness's checks would break when its API changed.
- **Put the code layout or tool-guide template in `rules.md`.** Makes one project's structure, or example text, part of the trust contract, which a pass doesn't depend on.
- **Copy the formats into every harness beside `rules.md`.** More unchanged copies to keep in step, and a new folder in the fixed layout.
- **Identical copies in both skills, with a test that they match.** Two sources for one format, and verify-change still never sees the feature-map format.

## What changes

`rules.md` gains the Feature map section, about 750 words, read only by skills that edit the map. `harness-code.md` lives in add-feature-checks, with `doctor.md`, `harness-components.md`, verify-change's section list, audit-coverage's requirements pointer, and USAGE.md following. Existing harnesses get the new `rules.md` by swapping the file.
