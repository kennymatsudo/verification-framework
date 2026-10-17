# Discovery prompt

Spawn one read-only subagent on a mid-tier model with this prompt. Fill in the repo path, target, and any saved findings.

---

Read the repo at `<repo path>` and answer each question below from its code, scripts, and docs. Do not run the app, its tests, or a build. Do not edit files.

Target: `<app or system>`.
Saved findings: `<matching Setup record, or none>`.

Scope discovery to this target. Follow workspace and startup configuration into accessible referenced repos or setup folders. Recheck saved findings against their sources. Report competing setup candidates separately; do not choose an unrelated app's startup command.

For every answer, cite `path:line`. If the repo does not answer a question, write "Unknown" and name the places you looked.

1. **Start.** The repo's own command to run it locally (Makefile, package scripts, README quickstart, compose file). Ports, environment variables, seed data, test accounts, and auth it needs.
2. **Ready.** The signal that it is up: a health route, a log line, a port answering, a prompt.
3. **Who can start it.** Anything that needs a human: a cloud login, a VPN, a secret from a password manager, a hardware device. Say whether an agent with only this checkout could start it.
4. **Isolation.** Can two copies run side by side? Look for configurable ports, data directories, browser profiles, and shared external resources (one sandbox account, one webhook URL).
5. **Real side effects.** Anything a run would do outside this machine: send email or messages, charge money, create records in a shared sandbox, spend a quota.
6. **Requirements source.** Where acceptance or launch requirements for this target live, if anywhere.
7. **Code repos.** List every checkout whose code the running path uses, including a separate setup or harness repo when its code decides the verdict. For each, name the portable source of its checkout path (config key, compose file, or relative path), its default branch, and how the project identifies the version the running process loaded. Mark any version it cannot identify as unknown.

Return the seven answers in order, then required setup unknowns, sources inspected, and the next information needed. Distinguish missing instructions from instructions that exist but need an unavailable checkout, account, or human action. An absent optional tool is not a missing startup instruction. Name anything that looked broken (a start command that references a missing file, a stale README step).
