# Settings template

Write this into the harness as `settings.md` and replace each `<...>` with what the repo uses. It holds the app's repos, requirements source, and commands. Artifact locations are fixed by `rules.md`, which is copied unchanged. `scripts/check.py` reads the labeled lines, so keep each label exact. Ready settings need every listed line; incomplete settings omit unknown required fields.

---

```markdown
# <App> verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: incomplete

Use `incomplete` until doctor proof exists. Set `ready` to run the map check, keeping it only if that check passes. Keep setup findings, blockers, the resume action, and doctor proof in `status.md`'s named Setup section. A verification run stops on incomplete setup.

## Workflow

- Requirements source: <source, or none>

## Repos

- <repo name>: <path relative to the harness's Git root, or env:<env file relative to that root>:<key>>

List every repo whose code a check runs, including this repo when it owns running code. A single-repo harness has one line, such as `- app: .`. An `env:` locator reads a checkout path from an existing project settings file at run time; do not save a developer's absolute path here.

## Commands

- Start: <start command>
- Doctor: <doctor command>
- Ready line: <the exact line the doctor prints when ready>
- Probe: <probe command, or none yet>
- Invariants module: <path, or none yet>
- Settle signal: <what shows the app has settled, or none>

The probe and invariants module read and judge state without importing app code. Record working directories and startup notes beside these commands: whether the agent may start the app, and any prompt, personal login or credentials, or approval that requires the user. An existing non-local environment still needs a doctor that identifies its running code and explicit action permissions.
```
