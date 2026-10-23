# Template for `verify-<app>/README.md`

Fill the app name, surface, and commands from discovery and `settings.md`. This is the page a person sees when they open the harness folder, including on GitHub, so write it for a teammate who has never heard of the framework. Keep it to what they act on; the files it links hold the details.

---

```markdown
# Verify <app>

This folder proves changes to <app> work by driving the running <surface> and reading back the result. An AI agent uses it through the `verify-<app>` skill; you can use it directly too.

- **Verify a change:** ask your agent to "verify my change to <app>".
- **See what passed and failed:** [status.md](status.md). Known limits and untested cases are in [notes.md](notes.md).
- **See how each check last ran, and watch recordings:** open [recordings.html](recordings.html) in a browser.
- **See what's covered:** [the feature map](features/README.md).
- **Debug by hand:** [tools.md](tools.md) lists every command. Check the app is up with `<doctor command>`.

Keep a passing run's video by running a check with `VERIFY_KEEP_RECORDING=1`. A failed run keeps its video on its own.

Files in `scripts/framework/` and `rules.md` are copied from verification-framework and are never edited here.
```
