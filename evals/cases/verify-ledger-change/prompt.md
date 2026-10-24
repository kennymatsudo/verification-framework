---
tags: [smoke, verify]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

I'm on branch feature/statement-memo-filter: the last commit lets the statement be filtered by memo (GET /accounts/<id>/statement?memo=...). Verify my change with the verify-ledger skill (the harness is at .claude/skills/verify-ledger). Use the existing checks only.
