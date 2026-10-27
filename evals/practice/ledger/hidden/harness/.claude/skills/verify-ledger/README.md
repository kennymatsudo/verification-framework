# Verify ledger

This folder proves changes to ledger work by driving the running HTTP API and reading back the result from its database. An AI agent uses it through the `verify-ledger` skill; you can use it directly too.

- **Verify a change:** ask your agent to "verify my change to ledger".
- **See what passed and failed:** [status.md](status.md). Known limits and untested cases are in [notes.md](notes.md).
- **See how each check last ran:** open [recordings.html](recordings.html) in a browser.
- **See what's covered:** the feature files in `features/`, one per feature; [status.md](status.md) lists every behavior.
- **Debug by hand:** [tools.md](tools.md) lists every command. Check the app is up with `python3 .claude/skills/verify-ledger/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8071/health"`.

Files in `scripts/framework/` and `rules.md`, and the `vf`, `vf-verify`, and `vf-explain` folders beside this one, are copied from verification-framework and are never edited here; vf's update mode replaces them all. Nothing to install: your agent finds the skills in this repo.
