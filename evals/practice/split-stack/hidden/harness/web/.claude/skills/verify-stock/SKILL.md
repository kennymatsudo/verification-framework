---
name: verify-stock
description: >-
  Prove a change to stock works by running the real command against the running API and reading back
  what the API stored, with evidence. Use before handing back any change to stock's
  user-facing behavior, when asked to verify, prove, or check a stock feature, or
  when asked what stock checks exist.
---

# Verify stock

You own verification of changes to stock. Use this skill's directory as the app's verification harness.

## 1. Delegate verification

Load the vf skill by name and give it this harness directory, the change to verify, and the user's scope and restrictions, including any existing-checks-only request. Ask it for verify-pr mode when the user asked to verify a pull request, by its link or number or by calling it a pull request, and for verify mode otherwise. A copy of vf sits beside this skill in the same skills directory, so a clone of the repo has it. If it is unavailable anyway, stop and say the harness owner restores it by running vf's update mode from an installed framework; do not invent a local procedure.

Done when vf has returned the report, or the missing dependency is named.

Reply: the verification report from vf, or the update step needed.
