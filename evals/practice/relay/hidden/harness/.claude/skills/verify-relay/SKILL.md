---
name: verify-relay
description: >-
  Prove a change to relay works by running the real command on input files and reading back
  what it wrote, with evidence. Use before handing back any change to relay's
  user-facing behavior, when asked to verify, prove, or check a relay feature, or
  when asked what relay checks exist.
---

# Verify relay

You own verification of changes to relay. Use this skill's directory as the app's verification harness.

## 1. Delegate verification

Load the vf skill by name in verify mode and give it this harness directory, the change to verify, and the user's scope and restrictions, including any existing-checks-only request. A copy of vf sits beside this skill in the same skills directory, so a clone of the repo has it. If it is unavailable anyway, stop and say the harness owner restores it by running vf's update mode from an installed framework; do not invent a local procedure.

Done when vf has returned the report, or the missing dependency is named.

Reply: the verification report from vf, or the update step needed.
