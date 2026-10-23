# Template for `verify-<app>/SKILL.md`

Fill the app name and surface from discovery.

---

```markdown
---
name: verify-<app>
description: >-
  Prove a change to <app> works by driving the running <surface> and reading back
  the result, with evidence. Use before handing back any change to <app>'s
  user-facing behavior, when asked to verify, prove, or check a <app> feature, or
  when asked what <app> checks exist.
---

# Verify <app>

You own verification of changes to <app>. Use this skill's directory as the app's verification harness.

## 1. Delegate verification

Load the vf-verify skill by name and give it this harness directory, the change to verify, and the user's scope and restrictions, including any existing-checks-only request. A copy of vf-verify sits beside this skill in the same skills directory, so a clone of the repo has it. If it is unavailable anyway, stop and say the harness owner restores it by running vf's update mode from an installed framework; do not invent a local procedure.

Done when vf-verify has returned the report, or the missing dependency is named.

Reply: the verification report from vf-verify, or the update step needed.
```
