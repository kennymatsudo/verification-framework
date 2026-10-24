---
tags: [add-checks]
max_turns: 300
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

The verification harness for the kiosk is set up (see .claude/skills/verify-kiosk). Use vf-verify in add-checks mode to add checks for everything in REQUIREMENTS.md. The checks should drive the real page in a browser; Playwright with Chromium is installed.
