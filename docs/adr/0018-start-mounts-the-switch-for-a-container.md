# ADR 0018: Start mounts the switch for an app in a container

Status: Accepted. 2026-11-15. Extends [ADR 0017](0017-switched-breaks-share-one-restart.md); replaces nothing in it.

## Problem

A switched break's gate reads the break session's switch file, which lives in the repo's private Git folder on the host. On the first converted app, the breaks a switch should help most sit in a service that runs in a Docker container with its code built into the image. The container can't see the host's Git folder, so a gate there would never turn on and every break would miss. The harness can't fix this alone: to find the file, its Start would have to read the session folder, which the `break-aware` smell flags so that no harness code can tell a break is on.

## Decision

- **The switch file sits alone in a folder.** `vf.py break start` writes it as `gate/switch` in the session folder and prints that path, as before.
- **Stop and Start get that folder.** Whenever `vf.py break` points the app at the session's copy, it sets `VERIFY_BREAK_SWITCH_DIR` to the folder for those two commands only. Pointing back at the developer's checkout leaves it unset.
- **An app in a container mounts it at the same path.** Its Start mounts the folder read-only at the identical absolute path inside the container, so a gate reads the path `break start` printed wherever the code runs. The folder is mounted, not the file, because each switch replaces the file and a mount of a single file keeps the old one.
- **The smell still guards checks.** `smells.py` matches whole names, so a Start reading `VERIFY_BREAK_SWITCH_DIR` is not `break-aware`; a check never receives the variable.

The first switched run or control always restarts the app, so the mount is in place before any gate runs, in place or in a scratch copy.

## Options we passed on

- **Let `harness.json` say where the switch file lives.** A setting that only moves the problem, and every harness must learn it.
- **The framework mounts it for each container runtime.** One option per runtime; how an app starts belongs to the harness.
- **Mount the whole session folder.** It holds the session record and the saved edits, which a container has no need to see.
- **Serve the switch over the network.** More moving parts, and it sits close to injecting faults from outside the app.

## What changes

- `break_session.py`: `switch_dir`, `VERIFY_BREAK_SWITCH_DIR` for Stop and Start when they point at the copy, and its `--help`. `smells.py` matches whole names. Unit tests in `test_break_session.py` and `test_smells.py`.
- `rules.md` (Planned breaks) and `references/harness.md` (the restart-cost advice) say how an app in a container mounts it. The Rules version stays 10: a harness with no container is asked to do nothing new.
- USAGE.md, `docs/internals.md`, and `docs/design.md`. No eval case: a practice repo can't depend on Docker, so the unit test carries the behavior.
