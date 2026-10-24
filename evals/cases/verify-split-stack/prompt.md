---
tags: [verify]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

Two repos are checked out side by side: web/ (the stock command-line client, with the harness at web/.claude/skills/verify-stock) and api/ (the Go API). On api's branch feature/normalize-names the last commit trims whitespace around item names. Verify that the stock client still works, with the verify-stock skill and existing checks only.
