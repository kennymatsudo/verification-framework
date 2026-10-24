---
name: vf-verify
description: >-
  Verify a change on the real app with its verification harness, and build the
  proof the harness lacks: checks for a feature, and the probes and actions they
  need, each proven on the real app. Use when a verify-<app> skill delegates
  here, or for "verify this change", "check checkout on this branch", "add
  checks for checkout", "what should we add next?", "add this script as a tool",
  "let agents look up an order". Use vf to set up a harness or keep one honest,
  and vf-explain to ask how far to trust a pass.
---

# Verify

You own the claim that a change works, backed by evidence a reviewer can rerun, and the proof the harness lacks for it. The app's harness owns its commands and proof rules. Work in one of three modes:

- **verify:** prove a change or a named feature on the requested version, and record the results.
- **add-checks:** agree on a feature's behavior, build its checks, and prove each can fail on a planned break.
- **add-tools:** build a probe or action apart from any check, and prove it on the real app.

## 1. Pick the mode

Take the mode the calling skill or the request names, or the one it plainly fits: a change or feature to verify, or a `verify-<app>` handoff, is verify; "add checks for" or "what should we add next?" is add-checks; a script, request, or question to turn into a probe or action is add-tools. Verify delegates missing proof to add-checks within the agreed scope, and add-checks loads add-tools for each probe or action a check needs. An explicit existing-checks-only request keeps verify from building.

Done when one mode is chosen.

## 2. Run the mode

Read the mode's procedure and follow every step: `references/mode-verify.md`, `references/mode-add-checks.md`, or `references/mode-add-tools.md`. Read only the chosen mode's file and the references it names; a mode that hands off to another reads that one when it gets there.

Done when the mode's procedure reached its last step, or stopped with the reason it gives.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.

Reply: the reply the mode's procedure ends with.
