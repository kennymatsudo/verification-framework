# ADR 0007: The framework ships inside the app's repo

Status: Accepted. 2026-10-23.

## Problem

A harness is built once by one person and then used by every teammate who changes the app, through their agent. Each harness already carries its own `rules.md` and `vf.py`, but the skills that drive it live on each person's machine. A teammate who never installed the framework asks their agent to verify a change, and the generated `verify-<app>` skill stops and asks them to install vf-verify, a tool they've never heard of. The agent can still report done with nothing behind it, which is the moment the framework exists to prevent. Teammates who did install it can run different versions of the procedure against the same harness, and nothing notices unless the gap is so wide that the harness's `vf.py` lacks `validate`.

## Decision

The framework's three skills are committed into the app's repo, so a clone is the install.

- **One copy of the skills, and still one copy of the scripts.** `vf.py sync` copies vf, vf-verify, and vf-explain into the skills directory that holds the harness, without their `scripts/` folders, and records their hashes in `framework.sha256` the way it records `rules.md` and `scripts/framework/`. sync copies every framework script into the harness's `scripts/framework/`, which today holds seven of the twelve, and a committed skill calls each script there, so the repo holds one pinned copy of each. Only an installed skill carries `scripts/`, because sync must run from somewhere before a harness exists. Several harnesses in one skills directory share the copy. Teammates get verify, add-checks, explain, audit, and verify-pr with nothing to install; setup comes along and is harmless, since vf runs only when a person calls it.
- **The committed copy reads as vendored.** sync skips `__pycache__`, and the harness `README.md` says the sibling vf, vf-verify, and vf-explain folders are framework copies that vf's update mode replaces and nobody edits by hand. The framework README's Install section recommends marking the skills directory `linguist-vendored` in `.gitattributes` and excluding it from the project's linters; skills recommend this and never edit Git files themselves.
- **The owner updates.** Whoever owns the harness installs the framework and runs vf's update, which refreshes every copy in one commit. The plugin install suits the owner best: its skills are namespaced, so `/vf` runs the repo's copy and `/verification-framework:vf` runs the newer one that updates it. A committed vf asked to update says that updating needs the framework installed and prints the install command, instead of syncing from itself and reporting nothing to do.
- **Global installs are allowed, and a version check catches a mismatch.** Which copy an agent loads when a personal install and a project copy share a name differs by agent. Whichever wins, it can't change a verdict, because records and verdicts come from the harness's own `vf.py` and `rules.md`, but the procedure can differ. Every skill states the Rules version it was written for and passes it to `vf.py validate`, which fails on a mismatch and says which side to update: the harness when the skill is newer, the install when the harness is newer.
- **Every agent the team uses gets a copy.** When those agents read different skills directories, sync writes the three skills into each known skills directory that exists at the project root and hashes every copy, so the version check catches one that drifts.

## Options we passed on

- **Install only, with a clearer install message.** Simplest, but fails every teammate who didn't install, at the moment that matters.
- **Commit vf-verify and vf-explain only.** Teammates also audit and verify pull requests, and that's vf.
- **Commit each skill with its own `scripts/`.** Two copies of `vf.py` in one skills directory, which drift; [ADR 0006](0006-one-versioned-tool-writes-every-record.md) pins one.
- **Split setup into its own skill so teammates don't get it.** A new skill for a job, not for a new kind of person starting it, which [ADR 0002](0002-three-skills.md) rules out; setup is harmless to ship.
- **Tell people not to install globally.** Hits evaluators and champions, the people who spread the framework, and a skimmed warning protects nobody.
- **A global copy that hands off to the repo's copy at the start of every run.** Depends on agents reliably switching instructions mid-run, which is untested, where a version check is a script with a clear pass or fail.
- **Symlink the other agents' skills directories to one copy.** Breaks on Windows without `core.symlinks`, and whether each agent follows a link is untested.
- **Check the skills' hashes instead of a Rules version line.** Stricter, since it would catch a procedure change that bumps no rule, and a possible follow-up; the version line catches the mismatch this ADR is for.

## What changes

`vf.py sync` (skills copy without `scripts/`, `__pycache__` skipped, several skills directories) and `framework.sha256`; `FRAMEWORK_SCRIPTS` gains `locate.py`, `break_checks.py`, `smells.py`, `weakened.py`, and `trust_facts.py`, and every skill body calls them under `<harness>/scripts/framework/`; `validate.py` (Rules version check); vf's setup and update modes, including the committed copy's update message; the shared gate sentence in every skill and `tests/test_preamble.py`; the generated `verify-<app>` entry point's missing-skill message; `rules.md` (Harness layout; the Rules version rises); the harness `README.md` template; README's Install section; USAGE.md; internals.md; and architecture.md.
