# Settings template

Write this into the harness as `settings.md` and replace each `<...>` with what the repo uses. It holds the app's repos, requirements source, and commands. Artifact locations are fixed by `rules.md`, which is copied unchanged. `scripts/framework/vf.py validate` reads the labeled lines, so keep each label exact. Ready settings need every listed line; incomplete settings omit unknown required fields.

---

```markdown
# <App> verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: incomplete

## Workflow

- Requirements source: <source, or none>

## Repos

- <repo name>: <path relative to the project root, or env:<env file relative to the project root>:<key>>

List every repo whose code a check runs, including this repo when it owns running code. A single-repo harness has one line, such as `- app: .`. The project root is the folder holding the skills directory this harness sits in; in a monorepo, `.` is the app's own folder, so dirty state covers only that folder. An `env:` locator reads a checkout path from an existing project settings file at run time; do not save a developer's absolute path here.

## Commands

- Start: <start command; or none when each check starts the app itself, or user when only a person can start it>
- Stop: <command that stops what Start started and removes its launch record, or none>
- Doctor: <doctor command; vf.py run runs it from the project root before every check>
- Ready line: <the exact line the doctor prints when ready>
- Probe: <probe command, or none yet>
- Reloads: <yes when the app picks up an edit to its checkout without a restart, no when it must be restarted>

The probe reads state without importing app code. Record working directories and startup notes beside these commands: whether the agent may start the app, and any prompt, personal login or credentials, or approval that requires the user.

Start may name a repo's checkout as `{checkout:<repo name>}`. On an ordinary run `vf.py` fills it with that repo's checkout; during a planned break it fills the broken repo's placeholder with the scratch copy and every other with its own checkout, so the one Start command both launches the app and points it at scratch code. Every command also runs with `VERIFY_CHECKOUT_<REPO>` set for every repo (the name in capitals, other characters as underscores), naming the checkout the run records, so a doctor or check that runs the code itself runs it from there. A `{checkout:<repo>}` that reaches the app must load the scratch files, not this checkout's: start the copy's entry file by path, or put the checkout first on the module path. `python3 -m <package>` from the project root imports this checkout even with `PYTHONPATH` set, so a break in the copy never reaches the app.

When the app runs the checkout's files directly, the framework's launcher can fill the first three lines, so no app-specific doctor code is needed: `Start: scripts/framework/vf.py start --until "<ready probe>" -- <app command reading {checkout:<repo>}>`, `Stop: scripts/framework/vf.py stop`, and `Doctor: scripts/framework/vf.py doctor --probe "<ready probe>"`, where the ready probe is a shell command that exits 0 once the app answers, such as a request to its health URL. An app that reloads on edit, runs in a container built from a cache, or compiles first needs its own doctor, which may still call `vf.py doctor` for the process and the code on disk. Set `Reloads: yes` for an app that picks up an edit to its checkout without a restart, so a planned break skips the restart; otherwise `no`.

Reaching a real external or shared system requires the user's approval for that run. An existing non-local environment still needs a doctor that identifies its running code and explicit action permissions.

For a planned break, `scripts/framework/vf.py break` runs Stop and then Start from the project root to point the app at the scratch copy, and again at the developer's checkout when the session ends; with `Reloads: no` it also restarts between breaks. `Start: none` means each check starts the app itself from `VERIFY_CHECKOUT_<REPO>`, so a break needs no restart. `Start: user` means only a person can start the app, so planned breaks are blocked; record the proof as Not break-tested. Start must name a `{checkout:<repo>}` that reaches the broken repo's code, or the break runs against unchanged code and is not credited.

When code has uncommitted changes, capture `code_state.py`'s `dirty_hash` at launch and compare it along with the commit, rather than relying on the dirty flag alone.
```
