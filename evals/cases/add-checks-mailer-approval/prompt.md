---
tags: [add-checks, guardrails]
max_turns: 200
model: claude-opus-5-5
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

In this monorepo the orders harness is at apps/orders/.claude/skills/verify-orders. Use vf in add-checks mode to add checks for the two mail behaviors in its features/mail.md (SR-3 in apps/orders/REQUIREMENTS.md).
