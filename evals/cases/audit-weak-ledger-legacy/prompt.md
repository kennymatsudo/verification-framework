---
tags: [smoke, audit]
max_turns: 200
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

/verification-framework:vf Are our QA checks fake? Audit the smoke checks under qa/ with the weak-checks audit. Don't change anything; just tell me which checks would pass on broken code and why.
