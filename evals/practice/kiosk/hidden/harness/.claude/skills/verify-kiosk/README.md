# Verify kiosk

This folder proves changes to the kiosk work by driving the real page in a browser and reading back what it stored. An AI agent uses it through the `verify-kiosk` skill; you can use it directly too.

- **Verify a change:** ask your agent to "verify my change to the kiosk".
- **See what passed and failed:** [status.md](status.md). Known limits and untested cases are in [notes.md](notes.md).
- **See how each check last ran, and watch recordings:** open [recordings.html](recordings.html) in a browser.
- **See what's covered:** the feature files in `features/`, one per feature; [status.md](status.md) lists every behavior.
- **Debug by hand:** [tools.md](tools.md) lists every command. Check the app is up with `python3 .claude/skills/verify-kiosk/scripts/framework/vf.py doctor --probe "curl -sf http://127.0.0.1:8072/api/health"`.

Keep a passing run's video by running a check with `VERIFY_KEEP_RECORDING=1`. A failed run keeps its video on its own.

Files in `scripts/framework/` and `rules.md`, and the `vf` folder beside this one, are copied from verification-framework and are never edited here; vf's update mode replaces them all. Nothing to install: your agent finds the skill in this repo.
