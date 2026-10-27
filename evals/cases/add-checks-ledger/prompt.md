---
tags: [smoke, add-checks]
max_turns: 300
model: claude-opus-5-5
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

The verification harness for this app is set up (see .claude/skills/verify-ledger). Use vf in add-checks mode to add checks for everything in REQUIREMENTS.md. Ask me about anything the requirements leave open.
