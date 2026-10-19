# Discover and resume setup

Discover an existing way to run the target before building verification tools. Keep a sourced setup distinct from one proven against the real system.

## Resolve missing setup

Read the project's instructions, startup scripts, workspace configuration, and setup docs, following references into accessible setup folders and repos. Read a candidate command's script to learn what it starts, what it needs, and what it changes. When one setup fits the target, proceed with it.

Otherwise ask only what the project could not answer, one question at a time, with a recommendation when the sources support one: which of several setups matches the user's workflow, how they run the target when you found nothing (say where you looked), or where a missing checkout, account, or human action lives. Never ask for secret values. Creating a development environment is a separate job from creating a harness; without the user's direction to do it, save the blocker and stop. A question the user can't answer, or a known procedure that can't run now, leaves setup incomplete with a named blocker, never a guessed command.

A step needs a human only when its script prompts, needs their login or credentials, or has a side effect they have not approved. Confirm those steps, and anything with a real side effect, before running them.

Before completing the skeleton, show the developer a short setup note as a plan to approve, following Messages in `rules.md`. It says only what the user acts on: how you will start the app, anything that needs them (a prompt, a login, a human-only step), and anything that touches shared state, plus what you won't run. It asks only when something needs approval: a step only the user can do, or driving a shared environment. Starting the app on this machine with its own port and data needs none. When nothing does, skip the note and continue. The developer doesn't act on the harness layout, the doctor's internals, or the requirements source, so leave them out. For example:

```
I found how to start your app: `docker compose up` in dev/. I'll start it myself, then build and test a readiness check against it.
I won't run `make seed`, which writes to the shared staging database.

Needs you: starting it opens a cloud login only you can complete. Will you sign in when it prompts? I recommend yes; it signs in only this machine. Then I'll start it and build the check.
```

Keep framework artifacts inside the new harness. Existing project documents can supply acceptance sources, but do not become alternate results or feature-map locations. Do not ask about Git tracking or modify ignore files.

## Save and resume

Stable facts go in `settings.md`: commands and their working directories, repo locators, prerequisites, and readiness signals. Store locators from project configuration, not machine-specific paths or credentials. The doctor's code validates readiness and running versions.

Save findings and blockers under `## Setup: <harness directory name>` in the harness's `status.md`, for example `## Setup: verify-storefront`. Read the record before repeating discovery.

Use the Setup record in `references/status.md`, replacing every placeholder with a fact or an explicit unknown.

Keep longer findings or doctor output in paragraphs or linked files under the same section. Update the record after an answer or attempted startup, and before returning with a blocker. The record holds what is true now, not how setup got there: replace a finding that changed, and drop resolved blockers and one-time events, since Git keeps the history. A workaround for one machine goes to the user in the reply, not into the harness. Preserve unrelated results. A new setup-verification session does not trust saved readiness or replay approvals from another session.

## Mark completion

Settings have `## Setup` with `- Status: incomplete` or `- Status: ready`. Keep it incomplete while required instructions are unknown, startup is blocked, or doctor proof is missing. Never fill a required command with `none yet` to make setup look complete.

If startup fails, inspect the failure and update the Setup record; ask only for the missing information or human action. If a human must start it, ask them to do so. If they cannot, save the blocker and resume action and report the doctor as unproven.

After the real doctor's output and tested code are recorded in Doctor proof and required settings are filled, clear Blocker and Next action to `none` and set Status to `ready` to run `validate.py`, the map check. Fix structural errors; keep ready only when that check passes. If it cannot pass, restore incomplete and record the blocker and resume action.
