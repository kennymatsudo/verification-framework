# Harness code layout

A layout that works well for the code in a harness's `scripts/`, written in the project's language. It is a recommendation: when the harness or project already organizes this code, extend that instead of adding a parallel one. Whatever the layout, the code follows `rules.md`: reads that judge state import no app code, a check and a probe that need the same fact call the same read function, and the evidence file is written before cleanup.

Start with what the first tool needs: the doctor needs connections, a probe adds reads, and the first check adds the run recorder. Add the other modules when a tool first needs them.

## Modules

- **Connections.** Where systems live and how to reach them: settings and credential loading, base URLs, database connections, HTTP clients, log locations. Other modules ask it for a connection instead of opening their own.
- **Reads.** One named function per fact a verdict, probe, or invariant relies on, named after the thing it reads (`order`, `messages_for_conversation`), never the table or route. A read returns "not found" only when the record is truly absent (no row, a 404) and raises on any other failure, so an outage never looks like a missing record.
- **Invariants.** Pure judging functions, as `rules.md` defines.
- **Actions.** One wrapper per system a user or operator touches, named for that system as they know it. Each method drives a real entry point. A wait polls a read until the expected state appears or a timeout passes, and returns nothing on timeout so the check decides what that means.
- **Screen.** For an app with a screen, one wrapper around the project's browser or device driver. It records the run and saves the snapshots, console output, and failed requests that `rules.md` describes under Evidence, and adds an `action` mark for each user action. Most drivers record without a pointer; drawing one in makes the video easier to follow, as long as the drawn pointer takes no clicks and holds no text.
- **Run recorder.** Described below.
- **Commands.** Thin entry files for the doctor, probes, actions, and checks. They parse arguments, enforce the approval flag, and call the modules above, with `--help` that works before anything connects.

Unit tests cover each judging function with one passing and one breaking state.

## Run recorder

One object per check run that writes the evidence file, so each check doesn't reimplement the Checks rules. It starts each numbered step with a `step` mark, records and prints each assertion as it is decided, turns an error in one block into a failed check so independent later steps still run, fills `code` from `scripts/code_state.py` output for the checkout the running process loaded, records `stopped` and `created`, saves `passed: null` for a run that only observed, and names a kept video in `recording`. It writes the file through a temporary file and a rename.

Also useful: introduce a long ID once by its role ("first conversation") and print the role afterward; save how long each step and slow wait took, so a slow run shows where it waited; print what a pass does not show beside the verdict.
