# ADR 0001: One harness per app, in a fixed layout, covering every repo it runs on

Status: Accepted. 2026-10-13.

## Problem

A pass has to say what code it ran on and where its proof lives. Many apps span several repos (frontend, proxy, backend) and run from a separate setup folder, so recording one repo's commit misnames the code that ran, and the agent can't read or break code in the other repos. Letting each project choose where its feature map, results, and evidence live made every skill that reads a harness discover paths and handle several ownership rules, and each format change added another branch to every reader.

## Decision

Each app gets a verification harness: a `verify-<app>/` folder in one of the repo's skills directories that holds the proof rules, settings, feature map, checks, and evidence. "Harness" is the short form. verify-change is the shared procedure, not a harness.

- **Every repo it runs on.** `settings.md` lists the repos the harness covers; an app in one repo lists just that one, so both cases work the same way. Setup finds the repos the way the project already does (a doc, a compose file, an environment variable) and asks when it can't. It never saves a path that only works on one person's machine. Before each run the doctor finds every repo and stops if one is missing. Each result records every repo's commit, and a planned break edits a scratch copy of the repo that owns the behavior.
- **Fixed layout.** The harness owns `settings.md`, `features/`, `status.md`, `tools.md`, `scripts/`, and `evidence/`. Locations are not settings. Requirements and existing acceptance docs stay where they are and are linked, not copied. The team decides evidence retention and Git tracking; skills never edit ignore files.
- **One format.** Skills and `check.py` support only the current format. A harness that doesn't match fails `check.py` with a plain error, and setup builds a new one. No harness built with an earlier format is in use anywhere that matters.

## Options we passed on

- **One harness per repo.** A feature across repos would be split, and no result could name all the code it ran on.
- **Save commits at setup.** They'd be out of date after the next commit.
- **Require a folder layout across repos.** Most projects wouldn't match it.
- **Use a project's existing feature map or results file in place.** Every reader gains path discovery and a second set of ownership rules.
- **Copy existing feature docs into the harness.** Two copies that drift apart.
- **Choose evidence tracking during setup.** It's a team policy, unrelated to readiness.
- **Call it a kit, or a test harness.** "Kit" names a bundle, not a setup that drives an app and judges the result; "test harness" suggests it only runs tests.
- **Keep supporting older formats, or add a format version with an upgrade step.** A branch in every reader for harnesses nobody depends on. Add versioning when a harness in real use would break.

## What changes

`rules.md` (Harness layout, Code under test), the `settings.md` template's Repos section, `check.py`, and every skill that reads a harness. AGENTS.md says a contract change carries no compatibility for earlier harnesses. Setup takes longer, because it reads every repo.
