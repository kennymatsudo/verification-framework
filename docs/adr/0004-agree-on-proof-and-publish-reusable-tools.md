# ADR 0004: Agree on proof and publish reusable tools

Status: Accepted. 2026-10-09.

## Problem

A check can pass, and even catch a deliberate break, while proving the wrong behavior. Tools hidden behind verification instructions are also hard for an agent to find while debugging.

## Decision

Before building or running proof, show the behavior, real actions, observations, and exclusions, grounded in requirements or user answers. Ask about meaningful acceptance conditions the agent inferred; established conditions need no extra approval. Store the agreed plan apart from the generated check. A separate reviewer compares each new check with that plan, and the check must catch its planned breaks. Reports use the same behavior wording.

Publish ordinary repo-local CLI tools in the project's language and developer-tool conventions, with shared reads, `--help`, enforced permissions, and one tool guide, `tools.md`. Link the guide from the project's agent instructions only with permission. Tools support investigation outside verification; a probe's observation alone is not a verdict.

## Options we passed on

- **Let checks define acceptance.** A passing assertion can measure the wrong thing.
- **Ask approval for every established condition.** Repetitive questions teach people to stop reading.
- **Require MCP, or one language and CLI.** Adds infrastructure and duplicates the project's clients.
- **One skill per tool.** Adds discovery overhead without improving how the command behaves.

## What changes

Setup publishes the doctor as the first tool. add-feature-checks previews new proof, publishes later tools, and has new checks reviewed. verify-change previews scope before startup and mirrors it in results. `rules.md` gains the Verification plan and Tool discovery sections, and `check.py` checks declared tool paths and feature plans.
