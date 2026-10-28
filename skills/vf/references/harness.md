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
  "tools": {}
}
```

`repos` lists every repo whose code a check runs, including this repo when it owns running code. A single-repo harness has one entry, such as `"app": "."`. The project root is the folder holding the skills directory this harness sits in; in a monorepo, `.` is the app's own folder, so dirty state covers only that folder. An `env:` locator reads a checkout path from an existing project settings file at run time; never save a developer's absolute path here.

`start` may name a repo's checkout as `{checkout:<repo name>}`. On an ordinary run `vf.py` fills it with that repo's checkout; during a planned break it fills the broken repo's placeholder with the scratch copy and every other with its own checkout, so the one command both launches the app and points it at scratch code. Every command also runs with `VERIFY_CHECKOUT_<REPO>` set for every repo (the name in capitals, other characters as underscores), naming the checkout the run records, so a doctor or check that runs the code itself runs it from there. A `{checkout:<repo>}` that reaches the app must load the scratch files, not this checkout's: start the copy's entry file by path, or put the checkout first on the module path. `python3 -m <package>` from the project root imports this checkout even with `PYTHONPATH` set, so a break in the copy never reaches the app.

When the app runs the checkout's files directly, the framework's launcher can fill `start`, `stop`, and `doctor`, so no app-specific doctor code is needed: `scripts/framework/vf.py start --checkout <repo>={checkout:<repo>} --until "<ready probe>" -- <app command reading {checkout:<repo>}>`, `scripts/framework/vf.py stop`, and `scripts/framework/vf.py doctor --probe "<ready probe>"`, where the ready probe is a shell command that exits 0 once the app answers, such as a request to its health URL. An app that reloads on edit, runs in a container built from a cache, or compiles first needs its own doctor, which may still call `vf.py doctor` for the process and the code on disk. Set `reloads` to `true` for an app that picks up an edit to its checkout without a restart, so a planned break skips the restart.

Reaching a real external or shared system requires the user's approval for that run. An existing non-local environment still needs a doctor that identifies its running code and explicit action permissions.

For a planned break, `scripts/framework/vf.py break` runs `stop` and then `start` from the project root to point the app at the scratch copy, and again at the developer's checkout when the session ends; with `reloads` false it also restarts between breaks. In a worktree `vf.py break worktree` made, the break happens in place on the app already running it: the session starts with no restart, and the restart before each break and at the end is Stop and Start on that same worktree unless `reloads` is true, so a cheap `start` pays off once per break. A `start` of `none` means each check starts the app itself from `VERIFY_CHECKOUT_<REPO>`, so a break needs no restart. A `start` of `user` means only a person can start the app, so planned breaks are blocked; record the proof as `not_break_tested`. `start` must name a `{checkout:<repo>}` that reaches the broken repo's code, or the break runs against unchanged code and is not credited.

Each tool is an entry under `tools`, keyed by a short name; `references/tool-guide.md` gives the fields. `vf.py tools` writes `tools.md` from them.

When code has uncommitted changes, capture `code_state.py`'s `dirty_hash` at launch and compare it along with the commit, rather than relying on the dirty flag alone.
