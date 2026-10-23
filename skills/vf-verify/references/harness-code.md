# Harness code layout

A layout that works well for the code in a harness's `scripts/`, written in the project's language. It is a recommendation: when the harness or project already organizes this code, extend that instead of adding a parallel one. Whatever the layout, the code follows `rules.md`: reads that judge state import no app code, a check and a probe that need the same fact call the same read function, and each step is reported as soon as it is decided.

Start with what the first tool needs: the doctor needs connections, a probe adds reads, and the first check adds the reporter. Add the other modules when a tool first needs them.

## Modules

- **Connections.** Where systems live and how to reach them: settings and credential loading, base URLs, database connections, HTTP clients, log locations. Other modules ask it for a connection instead of opening their own.
- **Reads.** One named function per fact a verdict or probe relies on, named after the thing it reads (`order`, `payments_for_order`), never the table or route. A read returns "not found" only when the record is truly absent (no row, a 404) and raises on any other failure, so an outage never looks like a missing record.
- **Actions.** One wrapper per system a user or operator touches, named for that system as they know it. Each method drives a real entry point. A wait polls a read until the expected state appears or a timeout passes, and returns nothing on timeout so the check decides what that means.
- **Screen.** For an app with a screen, one wrapper around the project's browser or device driver. It records the run, keeps the video only as `rules.md` describes under Evidence (the run failed, or `VERIFY_KEEP_RECORDING=1` is set), saves the snapshots, console output, and failed requests from that section, and adds an `action` mark for each user action. Most drivers record without a pointer; drawing one in makes the video easier to follow, as long as the drawn pointer takes no clicks and holds no text.
- **Reporter.** Described below.
- **Commands.** Thin entry files for the doctor, probes, actions, and checks. They parse arguments, enforce the approval flag, and call the modules above, with `--help` that works before anything connects.

Unit tests cover each judging function with one passing and one breaking state.

## Reporter

A few lines, shared by every check, that append one JSON event per line to the file `VERIFY_REPORT` names, as the Evidence section of `rules.md` defines them. It writes the `check` event first, starts each numbered step with a `step` mark, reports each assertion as a `step` the moment it is decided with the sub-features it judges, turns an error in one block into a failed step so independent later steps still run, reports a `stopped` event and exits 2 when the run cannot reach a verdict, lists what the run made in `created` events, and names a kept video in a `recording` event. Files it keeps go in the folder `VERIFY_RUN_DIR` names. It writes no evidence file, reads no Git state, and runs no framework script: `vf.py run` builds the record, records the code, and builds the replay page.

A check written as an existing end-to-end test becomes a check through a reporter in that runner's own hook, as long as its reads that decide a verdict follow the Probes rules.

Also useful: report how long each step and slow wait took in `detail`, so a slow run shows where it waited; print what a pass does not show beside the verdict.
