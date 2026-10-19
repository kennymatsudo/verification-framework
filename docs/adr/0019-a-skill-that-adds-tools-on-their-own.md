# ADR 0019: A skill that adds tools on their own

Status: Accepted. 2026-10-18.

## Problem

A harness's tools, its probes (read-only questions) and actions (things a user or operator does), are standalone commands any agent can run. But the only skill that built them was add-feature-checks, which builds them on the way to a check. A tool wanted before any check, such as a script someone already wrote against a third-party API or an undocumented GraphQL call an agent found in another session, had no clear way in. Asking for an action on its own led into the feature plan, which expects behaviors to judge. The skill's name also hid the job from anyone looking for "add a tool".

Actions also refused to touch anything the harness didn't create. A tool that refunds a real customer's order, a record the user picked, could never run.

## Decision

- **A new skill, add-tools, owns probes and actions.** It builds them from the app's code, from a script or request found elsewhere, or by a route the user names (such as watching the browser's network requests), proves each on the real app, and publishes it in `tools.md`. It keeps the request the source found, rewrites the rest to the harness rules, and reads credentials from the project's settings, never from a captured request. A tool judges nothing, so it needs no feature plan or planned break.
- **add-feature-checks keeps what judges.** Feature files, checks, invariants, and scenarios. When a check needs a probe or action `tools.md` doesn't list, it loads add-tools by name. This narrows add-feature-checks' ownership in [ADR 0003](0003-each-skill-owns-one-part-of-verification.md).
- **Agents may invoke add-tools**, since add-feature-checks delegates to it and an agent mid-task may need a tool.
- **Guardrails on every tool.** `validate.py` checks each guide entry's fields and Help command (running it with `--run-help`) and flags a credential written into a tool or the guide. A mid-tier subagent reviews each new tool against the rules before it runs. A probe that reads the app's own API says so in its Limits, and a check judging that endpoint reads storage instead, since the API's answer is built by the code under test.
- **Actions may touch a record the user names.** Beyond what the harness created, an action may act on a record the user names by ID for this run, only with `--user-approved` and that ID passed in. It never picks such a record itself.

## Options we passed on

- **Detect app-code imports in `validate.py`.** It can't read imports reliably in every language ([ADR 0005](0005-judge-from-outside-the-app.md)); the review covers it.
- **A "tool on its own" branch inside add-feature-checks.** Works, but keeps the job behind a name about checks.
- **A skill that only imports outside tools.** Building from the app's code and from a found request end in the same proof and guide entry; two skills would split one job.
- **Keep the ownership rule and have the user copy records into harness-owned ones.** Many systems can't copy a real customer's order or account.

## What changes

A new `skills/add-tools/`. add-feature-checks' description, steps, and component guide drop probes and actions. `rules.md`'s Tool discovery, Probes, Actions, and ownership lines, `validate.py` and its tests, the tool guide template, setup-verification, explore-bugs, verification-framework's playbooks and skill list, AGENTS.md, README.md, USAGE.md, `docs/architecture.md`, and `docs/internals.md`.
