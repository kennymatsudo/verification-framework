# ADR 0001: One harness per app, in a fixed layout, anchored on its project root

Status: Accepted. 2026-10-21.

## Problem

A pass has to say what code it ran on and where its proof lives. Many apps span several repos (frontend, proxy, backend), and some are one folder of a larger repository. Letting each project choose where its feature map, results, and evidence live made every skill that reads a harness discover paths and handle several ownership rules, and each format change added a branch to every reader. Folders named for agents were unreadable to people: framework copies sat beside the app's own tools, and every run's record went into one flat pile named by timestamp. Settings named how to start the app but not how to stop it, so a crashed or killed instance left a launch record that blocked the next start.

## Decision

Each app gets one verification harness: a `verify-<app>/` folder in one of its skills directories, holding `rules.md`, `settings.md`, `README.md`, `recordings.html`, `features/`, `status.md`, `notes.md`, `tools.md`, `scripts/` with the framework's copies in `scripts/framework/`, and `evidence/` with one folder per check. Locations are not settings.

- **Project root.** The folder holding that skills directory is the project root: the repo's top folder for a single-repo app, or the app's own folder in a monorepo. Recipe commands run from it, settings resolve from it, and a repo locator that names a folder inside a checkout scopes dirty state to that folder. Skills find a harness by `verify-*/rules.md` in the skills directories of the current folder and each folder above it, nearest first.
- **Every repo it runs on.** `settings.md` lists the repos the harness covers; a single-repo app lists one. Setup finds them the way the project already does and never saves a path that works on one machine only. Every result records every repo's code, and a missing repo stops the run.
- **Commands.** Settings name Start, Stop, Doctor, and how to point the app at scratch code. Stop is required: the command that stops what Start started and removes its launch record, or `none` when only a person starts the app. Nobody kills an instance the harness started.
- **Ready means proven.** Settings become `ready` only once the real doctor has run and `vf.py validate` passes. Incomplete setup stops every other skill with the saved blocker and next action, so setup resumes from the harness, never from chat.
- **One format.** Skills and `validate.py` support only the current format. A harness that doesn't match fails validation with a plain error, and setup builds a new one.
- **Each format where its readers look.** The feature map format is in `rules.md`, which every skill that edits the map reads. The recommended code layout for harness tools lives with the add-checks mode, since nothing else reads it. Requirements and acceptance docs stay where they are and are linked, not copied.

## Options we passed on

- **One harness per repo.** A feature across repos would be split, and no result could name all the code it ran on.
- **A `Project root:` line in settings.** A second way to say what the harness's location already says, and one that can disagree with it.
- **Use a project's existing feature map or results file in place.** Every reader gains path discovery and a second set of ownership rules.
- **Make Stop optional, or let callers delete the launch record.** "No stop needed" and "never built" become indistinguishable, and every caller would need each harness's private layout.
- **Group evidence by date, or name run folders after the branch.** People look for a behavior, not a day; branches contain slashes and change.
- **Keep supporting older formats.** A branch in every reader for harnesses nobody depends on.
- **Put the code layout in `rules.md`.** One project's structure would become part of the trust contract.

## What changes

`rules.md` (Harness layout, Setup, Code under test), the `settings.md` template, `validate.py`, `locate.py`, and every skill that reads a harness. AGENTS.md says a contract change carries no compatibility for earlier harnesses.
