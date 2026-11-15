---
tags: [add-checks]
max_turns: 300
model: claude-opus-5-5
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

The verification harness for this app is set up (see .claude/skills/verify-ledger). Use vf in add-checks mode to add checks for the deposit, transfer, and statement requirements in REQUIREMENTS.md: LR-3, LR-5, LR-6, and LR-8.
