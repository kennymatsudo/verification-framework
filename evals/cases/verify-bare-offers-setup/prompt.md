---
tags: [smoke, verify, guardrails]
max_turns: 60
model: claude-opus-5-5
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

Verify on the running app that a transfer debits the source account and credits the destination by the same amount (REQUIREMENTS.md LR-5). Don't just read the code or run the unit tests; I want it proven on the real app.
