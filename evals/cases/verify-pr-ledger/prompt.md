---
tags: [verify]
max_turns: 200
model: claude-opus-5-5
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

/verification-framework:vf A teammate opened a pull request from branch feature/statement-memo-filter into main. Their description: "Adds ?memo=<text> to GET /accounts/<id>/statement so clients can filter the statement by memo. No change to existing behavior." Verify the PR with verify-pr mode (the harness is at .claude/skills/verify-ledger) and draft the review comment for me. Don't post anything.
