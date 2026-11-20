# Manifest template

Write this into the harness as `harness.json` and replace each `<...>` with what the repo uses. It holds everything a script reads about the app: setup status, the requirements source, repos, commands, and tools. Artifact locations are fixed by `rules.md`, which is copied unchanged. `scripts/framework/vf.py validate` checks every field, so keep the keys exact. A ready manifest needs every field below; an incomplete one may leave unknown required fields out. Prose about how the app starts, what needs a person, and where its data lives goes in `notes.md`.

---

```json
{
  "app": "<App>",
  "setup": {
    "status": "incomplete",
    "target": "<app or system, its known boundary, and the requested setup>",
    "findings": "<established facts with file:line or user-answer sources>",
    "looked_in": "<sources inspected, including places that did not answer the question>",
    "blocker": "<what prevents finishing setup>",
    "next": "<the answer or action needed to resume>",
    "doctor_proof": null
  },
  "requirements": "<source, or null>",
  "repos": {
    "<repo name>": "<path relative to the project root, or env:<env file relative to the project root>:<KEY>>"
  },
  "commands": {
    "start": "<start command; or none when each check starts the app itself, or user when only a person can start it>",
    "stop": "<command that stops what start started and removes its launch record, or none>",
    "doctor": "<doctor command; vf.py run runs it from the project root before every check>",
    "ready_line": "<the exact line the doctor prints when ready>",
    "probe": null,
    "reloads": false
  },
  "check_coverage": {},
  "tools": {}
}
```

`repos` lists every repo whose code a check runs, including this repo when it owns running code. A single-repo harness has one entry, such as `"app": "."`. The project root is the folder holding the skills directory this harness sits in; in a monorepo, `.` is the app's own folder, so dirty state covers only that folder. An `env:` locator reads a checkout path from an existing project settings file at run time; never save a developer's absolute path here. A run that tests a pull request doesn't edit a locator to reach its worktrees: `vf.py break worktree`, run from the harness copy that runs the checks, records each other repo's worktree outside the working tree, and every command that uses it says so.

`start` may name a repo's checkout as `{checkout:<repo name>}`. On an ordinary run `vf.py` fills it with that repo's checkout; during a planned break it fills the broken repo's placeholder with the scratch copy and every other with its own checkout, so the one command both launches the app and points it at scratch code. Every command also runs with `VERIFY_CHECKOUT_<REPO>` set for every repo (the name in capitals, other characters as underscores), naming the checkout the run records, so a doctor or check that runs the code itself runs it from there. A `{checkout:<repo>}` that reaches the app must load the scratch files, not this checkout's: start the copy's entry file by path, or put the checkout first on the module path. `python3 -m <package>` from the project root imports this checkout even with `PYTHONPATH` set, so a break in the copy never reaches the app.

When the app runs the checkout's files directly, the framework's launcher can fill `start`, `stop`, and `doctor`, so no app-specific doctor code is needed: `scripts/framework/vf.py start --checkout <repo>={checkout:<repo>} --until "<ready probe>" -- <app command reading {checkout:<repo>}>`, `scripts/framework/vf.py stop`, and `scripts/framework/vf.py doctor --probe "<ready probe>"`, where the ready probe is a shell command that exits 0 once the app answers, such as a request to its health URL. An app that reloads on edit, runs in a container built from a cache, or compiles first needs its own doctor, which may still call `vf.py doctor` for the process and the code on disk. Set `reloads` to `true` for an app that picks up an edit to its checkout without a restart, so a planned break skips the restart.

Reaching a real external or shared system requires the user's approval for that run. An existing non-local environment still needs a doctor that identifies its running code and explicit action permissions.

For a planned break, `scripts/framework/vf.py break` runs `stop` and then `start` from the project root to point the app at the scratch copy, and again at the developer's checkout when the session ends; with `reloads` false it also restarts before each break, apart from switched breaks, which share one restart. In a worktree `vf.py break worktree` made, the break happens in place on the app already running it: the session starts with no restart, and the restart before each break and at the end is Stop and Start on that same worktree unless `reloads` is true, so a cheap `start` pays off once per break. A `start` of `none` means each check starts the app itself from `VERIFY_CHECKOUT_<REPO>`, so a break needs no restart. A `start` of `user` means only a person can start the app, so planned breaks are blocked; record the proof as `not_break_tested`. `start` must name a `{checkout:<repo>}` that reaches the broken repo's code, or the break runs against unchanged code and is not credited.

Each break costs that Stop and Start on an app that doesn't reload, so on such an app every break that can be gated goes into one edit behind a switch, as the Planned breaks section of `rules.md` describe: a session of N switched breaks restarts the app 2 times in place and 3 in a scratch copy, where one restart per break takes N+1 and N+2. When the code a gate sits in runs in a container, `start` mounts `$VERIFY_BREAK_SWITCH_DIR` read-only at that same path in its container whenever the variable is set, such as `-v "$VERIFY_BREAK_SWITCH_DIR:$VERIFY_BREAK_SWITCH_DIR:ro"` or a Compose volume, and recreates the container so the mount takes effect. Code that runs only at startup, a migration, or a browser bundle can't be gated, and each such break still pays its own restart, so make the restart cheap as well. Cheapest first: set `reloads` to `true` for an app that watches its files; set `start` to `none` when each check can start the app itself from `VERIFY_CHECKOUT_<REPO>`, so a break needs no restart at all; otherwise set `stop` to `none` and write `start` as an idempotent command that restarts only the service loading `{checkout:<repo>}`, such as `docker compose up -d api`, rather than tearing down and rebooting the whole stack. The doctor still proves the loaded version in every case. The scratch copy a break uses is kept between sessions, so a restart there rebuilds only what changed.

`check_coverage` is optional: each key is a check command, with its arguments, and each value lists the further behavior IDs that command judges. The Checks section of `rules.md` says how `vf.py verify` uses it. Declare a locale or answer variant under the command that runs it, since a journey that skips the variant doesn't cover it. Review each declaration against the check's code, then confirm the selection with `vf.py verify <IDs> --plan` and prove it with a run on the app.

Each tool is an entry under `tools`, keyed by a short name; `references/tool-guide.md` gives the fields. `vf.py tools` writes `tools.md` from them.

When code has uncommitted changes, capture `code_state.py`'s `dirty_hash` at launch and compare it along with the commit, rather than relying on the dirty flag alone.
