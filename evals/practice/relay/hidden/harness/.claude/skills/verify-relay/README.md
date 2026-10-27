# Verify relay

This folder proves changes to relay work by running the real command on real input files and reading back what it wrote. An AI agent uses it through the `verify-relay` skill; you can use it directly too.

- **Verify a change:** ask your agent to "verify my change to relay".
- **See what passed and failed:** [status.md](status.md). Known limits and untested cases are in [notes.md](notes.md).
- **See how each check last ran:** open [recordings.html](recordings.html) in a browser.
- **See what's covered:** the feature files in `features/`, one per feature; [status.md](status.md) lists every behavior.
- **Debug by hand:** [tools.md](tools.md) lists every command. Check the tool runs with `python3 .claude/skills/verify-relay/scripts/doctor.py`.

Files in `scripts/framework/` and `rules.md`, and the `vf`, `vf-verify`, and `vf-explain` folders beside this one, are copied from verification-framework and are never edited here; vf's update mode replaces them all. Nothing to install: your agent finds the skills in this repo.
