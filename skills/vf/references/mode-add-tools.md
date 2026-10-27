# Add tools

Follow this when vf runs in add-tools mode. The Guardrails in vf's `SKILL.md` apply throughout.

You own the harness's probes and actions: each built, proven on the real app, and published in its tool guide, so any later check or agent can use it. A tool judges nothing, so it needs no feature plan or planned break. Feature files, checks, and scenarios belong to the add-checks mode.

## 1. Read the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.

Run `<harness>/scripts/framework/vf.py validate --written-for 7` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. Then read its `harness.json`, the Tool discovery, Probes, and Actions sections of `rules.md`, and `tools.md`.

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

Keep the call the source found: its endpoint, query, and parameters. Rewrite the rest to the Probes or Actions rules in the project's language. Read credentials from the project's connection settings, never from a captured request. One the project doesn't hold yet, such as a third-party API token or a browser session cookie, comes from an environment variable, which the tool may also load from the project's existing untracked settings file, such as `.env`. Name the variable in the entry's `environment` field with how to get it and when it expires. A missing one exits 2 with a `STOPPED:` line naming it. Ask the user to set it themselves rather than paste it into the conversation.

Add each command under `tools` in `harness.json`, with the fields the Tool discovery section names, in the shape of its existing entries, then run `scripts/framework/vf.py tools` to write `tools.md`. In `limits`, say where an outside call came from, and for an undocumented one, that it may change without notice. Set the manifest's `probe` command when the tool fills it.

Link the guide from the project instructions the agent actually loads, scoped to the app in a monorepo, when no pointer is there yet. Ask before editing an existing instruction file unless the user authorized that exact edit. Without permission, keep the guide, show the proposed pointer, and report discovery as not wired; never claim unrelated agents can find it.

Done when every agreed tool exists and `<harness>/scripts/framework/vf.py validate --run-help` passes.

## 4. Review each tool

Spawn a read-only subagent on a mid-tier model for a blind review. Give it the harness's `rules.md` Tool discovery, Probes, and Actions sections, each tool's files, manifest entry, and source, not your reasoning. It reports every rule in those sections the tool breaks, and confirms the two things only this session can know: the call matches its source, and the manifest entry matches the code. Fix every finding before running the tool, and ask the user when one changes what the tool may do.

Done when the review has no open findings.

## 5. Prove each tool

Run each command's `--help`, then its documented success and failure paths against the real app, and show the output. Each must match its manifest entry.

- **Probe:** a real ID exits 0 with its JSON; a made-up ID exits 1 with a hint. Confirm it only reads.
- **Action:** with the user's OK for this run, run it once and read the result back with a probe, building that probe first if none exists. Run it without the approval flag and show the refusal. For an action on named records, run it on an unnamed one and show the refusal.

Clean up only what this run created, stopping instances it started with the Stop command; name anything still open.

Done when every tool has passed its proof or has a named blocker.

## Guardrails for this mode

- Copy no cookie, token, or password from a captured request into a tool, guide, or evidence.
- Edit existing files outside the harness only when the user named them for this workflow or authorized the exact edit.

Reply: in the shape `references/messages.md` gives. One line per tool: what it answers or does, in words a user would use, and whether its proof passed or what blocked it. Then one line for test data left anywhere shared. Commands, IDs, and sources belong in `tools.md`. If the project-instruction pointer isn't wired, end with it as the `Needs you` question.
