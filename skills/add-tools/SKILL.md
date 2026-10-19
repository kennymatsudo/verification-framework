---
name: add-tools
description: >-
  Add a probe or action to an existing verification harness, before or apart from
  any check, so later checks and agents can use it. Builds it from the app's code,
  a script someone already wrote, or a request they found, proves it on the real
  app, and publishes it in the tool guide. Use for "add this script as a tool",
  "let agents look up an order", "turn this GraphQL call into a probe", "add an
  action that places an order as a shopper". Use add-feature-checks to add checks.
---

# Add tools

You own the harness's probes and actions: each built, proven on the real app, and published in its tool guide, so any later check or agent can use it. A tool judges nothing, so it needs no feature plan or planned break. Feature files, checks, invariants, and scenarios belong to add-feature-checks.

## 1. Read the harness

Use the app harness the user or calling skill supplied, or glob `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`). Ask which when several match. If none matches the named app, stop and name setup-verification.

Read its `settings.md` and the Tool discovery, Lanes, Probes, and Actions sections of `rules.md`, then run `<harness>/scripts/framework/validate.py`. If it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop. Then read `tools.md`.

Done when the harness, setup gate, and existing tools are known, or a named blocker stops the work.

## 2. Agree on each tool

For each requested tool, settle what it answers or does and where its call comes from:

- **The app's code.** Find what the project already has: API clients, CLI commands, and the modules that own database and external API connections.
- **Something found elsewhere.** A script, or a request someone captured, such as an undocumented GraphQL query. Read it before running it.
- **A route the user names,** such as watching the browser's network requests while using the app. Follow it. Driving the app to capture a call is itself an action, so ask first when that would change real or shared data.

When `tools.md` already has a tool that answers the question, say so and extend it rather than adding another. For an action, decide with the user whether it needs the approval flag (anything outside this machine, shared, paid, or rate-limited does) and whether it may act on records they name by ID.

Show one line per tool: its name, what it answers or does, its source, and its permissions. Continue when every tool is read-only and named in the request, or a calling skill passed permissions its agreed plan covers; otherwise wait for the user's OK.

Done when each tool has a question or task, a source, and agreed permissions.

## 3. Build each tool

Put new code where the harness already keeps that kind of code. With no layout yet beyond the doctor, keep connections in one module, one named read function per fact in another, one wrapper per system an action touches, and thin command files that parse arguments, enforce the approval flag, and call those. Name a probe after the thing it reads (`probe order <id>`), never the table or route.

Keep the call the source found: its endpoint, query, and parameters. Rewrite the rest to the Probes or Actions rules in the project's language. Read credentials from the project's connection settings, never from a captured request. One the project doesn't hold yet, such as a third-party API token or a browser session cookie, comes from an environment variable, which the tool may also load from the project's existing untracked settings file, such as `.env`. Name the variable in the guide's Environment line with how to get it and when it expires. A missing one exits 2 with a `STOPPED:` line naming it. Ask the user to set it themselves rather than paste it into the conversation.

Publish each command in `tools.md` in the shape of its existing entries. In the Limits line, say where an outside call came from, and for an undocumented one, that it may change without notice. Update settings when the tool fills a `none yet` line.

Done when every agreed tool exists and `<harness>/scripts/framework/validate.py --run-help` passes.

## 4. Review each tool

Spawn a read-only subagent on a mid-tier model for a blind review. Give it the harness's `rules.md` Probes and Actions sections, each tool's files, guide entry, and source, not your reasoning. For each tool it confirms: reads import no app code, and a read through the app's own API is named in Limits; a probe only reads; an action enforces the approval flag and its ownership rule; credentials come from the project's settings; the call matches its source; the guide entry matches the code. Fix every finding before running the tool, and ask the user when one changes what the tool may do.

Done when the review has no open findings.

## 5. Prove each tool

Run each command's `--help`, then its documented success and failure paths against the real app, and show the output. Each must match its guide entry.

- **Probe:** a real ID exits 0 with its JSON; a made-up ID exits 1 with a hint. Confirm it only reads and imports no app code.
- **Action:** with the user's OK for this run, run it once and read the result back with a probe, building that probe first if none exists. Run it without the approval flag and show the refusal. For an action on named records, run it on an unnamed one and show the refusal.

Clean up only what this run created, stopping instances it started with the Stop command; name anything still open.

Done when every tool has passed its proof or has a named blocker.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Copy no cookie, token, or password from a captured request into a tool, guide, or evidence.
- Edit existing files outside the harness only when the user named them for this workflow or authorized the exact edit.

Reply: in the harness's Messages shape. One line per tool: what it answers or does, in words a user would use, and whether its proof passed or what blocked it. Then one line for test data left anywhere shared. Commands, IDs, and sources belong in `tools.md`.
