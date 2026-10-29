---
type: llm
focus: trace
weight: 1
---

Before running any check, the agent listed the pull request's claims (at least the memo filter and "no change to existing behavior") and gave each one a verdict such as Add, Already covered, Add with a missing step, or Skip, as vf's verify-pr mode does. A run that went straight to verify mode's preview without a claim list fails.
