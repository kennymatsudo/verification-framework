# ADR 0010: A starting skill that runs the others

Status: Accepted. 2026-10-16.

## Problem

Five of our eight skills run only when a person types their name, and an agent never sees those skills' descriptions. So a plain request like "are our checks fake?" reaches nothing unless the person already knows to type `/audit-weak-checks`. Some jobs also span skills, such as setting up, adding a first feature, then verifying, and the person starts each step by hand.

## Decision

Add verification-framework, one skill to start from without knowing the others. The person types `/verification-framework` with any request. It looks at the repo first: whether a harness exists, and whether setup stopped partway. Then it picks a playbook, a fixed list of steps that runs our skills in order, and shows that plan in one message before the first step runs.

- **Opens skills by path.** It reads each sibling's `SKILL.md` directly, so the person-only skills stay person-only everywhere else. The person's call to verification-framework is the permission. It looks in `../<name>/` first, then the project's and the user's skills directories, and names any missing skill with its install command before a playbook starts. Paths inside a loaded skill are relative to that skill's folder.
- **Runs only when called.** Like setup and the audits, so it never competes with the app's verify skill for an ordinary "verify my change".
- **Named after the framework.** It covers every job, so no verb fits ([ADR 0008](0008-name-skills-by-verb-and-question.md)), and the framework name is the one name a person knows from installing it.
- **Playbooks for chains we've seen.** Add one when a sequence of skills has been run by hand on a real project.
- **The only exception.** It breaks the verb rule and the rule that skills name each other rather than give paths, because it can't work installed alone. Every other skill keeps both rules.

## Options we passed on

- **Recommend a skill and stop.** The person still types each next command, and chains stay manual.
- **Let the agent start the five person-only skills.** They would then start unprompted in any session.
- **Only improve the README table.** It can't see the repo, and it isn't in front of the person while they type to the agent.
- **explain-skills or verification as the name.** The first fits the verb rule but nobody would guess it; the second reads well but isn't the name people installed.
- **Stay on for the rest of the session.** Needs session state that a skill doesn't get for free; one call per task covers the need.

## What changes

A new `skills/verification-framework/` with its playbooks. AGENTS.md names the two exceptions. README and USAGE point newcomers to it first. Adding or renaming a skill also updates its playbooks. In a Claude Code plugin install, it's listed as `verification-framework:verification-framework`.
