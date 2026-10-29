---
tags: [verify]
max_turns: 200
model: claude-opus-5-5
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

I opened a pull request from branch feature/statement-memo-filter into main. My description says: "Adds ?memo=<text> to GET /accounts/<id>/statement so clients can filter the statement by memo. No change to existing behavior." Use the verify-ledger skill (the harness is at .claude/skills/verify-ledger) to verify my pull request, and draft the PR comment. Don't post anything.
