---
tags: [audit]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

/verification-framework:vf On branch feature/history-route the statement route was renamed to /accounts/<id>/history and a new GET /accounts list was added. What aren't we checking? Run the coverage audit on the harness at .claude/skills/verify-ledger. Report only; don't edit the harness.
