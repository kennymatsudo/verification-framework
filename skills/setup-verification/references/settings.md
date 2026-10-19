# Settings template

Write this into the harness as `settings.md` and replace each `<...>` with what the repo uses. It holds the app's repos, requirements source, and commands. Artifact locations are fixed by `rules.md`, which is copied unchanged. `scripts/framework/validate.py` reads the labeled lines, so keep each label exact. Ready settings need every listed line; incomplete settings omit unknown required fields.

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

- Start: <start command>
- Stop: <command that stops what Start started and removes its launch record, or none when only a person starts the app>
- Doctor: <doctor command>
- Ready line: <the exact line the doctor prints when ready>
- Probe: <probe command, or none yet>
- Invariants module: <path, or none yet>
- Settle signal: <what shows the app has settled, or none>
- Run scratch code: <command that points the running app at the checkout {checkout} of repo {repo}; per check, when each check starts the app itself; or none>
- After an edit: <reloads, or the command that restarts what runs repo {repo} from {checkout}>

The probe and invariants module read and judge state without importing app code. Record working directories and startup notes beside these commands: whether the agent may start the app, and any prompt, personal login or credentials, or approval that requires the user.

Lane 2 covers local reads and actions; reaching a real external or shared system requires lane 3 approval. An existing non-local environment still needs a doctor that identifies its running code and explicit action permissions.

After switching or reloading code, the doctor must confirm the app loaded the requested version. `scripts/framework/break_session.py` runs the last two commands from the project root for planned breaks: Run scratch code with the scratch copy when a session starts and with the developer's checkout when it ends, and After an edit before each break's check. Use `none` when the app can't run another checkout: one instance per machine, a start only a person can do, or a shared environment. Planned breaks are then blocked.

When code has uncommitted changes, capture `code_state.py`'s `dirty_hash` at launch and compare it along with the commit, rather than relying on the dirty flag alone.
```
