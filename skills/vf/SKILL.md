---
name: vf
description: >-
  Verify a change on the real app with its verification harness, and build the
  proof the harness lacks: checks for a feature, and the probes and actions they
  need, each proven on the real app; or explain how far to trust a pass. Use
  before claiming a change works, when a verify-<app> skill delegates here, or
  for "verify this change", "prove it on the running app", "check checkout on
  this branch", "add checks for checkout", "what should we add next?", "add this
  script as a tool", "can I trust these checks?", "how is checkout checked?".
  With no harness yet, offer setup and build nothing. Setting up or updating a
  harness, auditing it, and verifying a teammate's pull request are jobs a
  person starts by name, such as "/vf set up verification for this app".
---

# Verification framework

You own getting a request to the right job, run by its own procedure. Every job is a mode of this skill, with its procedure in `references/mode-<name>.md`. Four modes start only when the person asks for that job by name in this session: setup, audit-coverage, audit-weak-checks, and verify-pr. The other four, verify, add-checks, add-tools, and explain, an agent may start for its own change or question.

## 1. Pick the mode

Match the request to one mode:

| Mode | When | Who starts it | File |
| --- | --- | --- | --- |
| setup | "Set up verification", "resume setup", "update the harness", "I updated the framework" | The person | `references/mode-setup.md` |
| verify | "Did my change work?", "verify checkout", a `verify-<app>` handoff | Anyone | `references/mode-verify.md` |
| add-checks | "Add checks for search", "what should we check next?" | Anyone | `references/mode-add-checks.md` |
| add-tools | "Add this script as a tool", "let agents look up an order" | Anyone | `references/mode-add-tools.md` |
| explain | "Can I trust these checks?", "how is checkout checked?", "what does verify-shop check?" | Anyone | `references/mode-explain.md` |
| audit-coverage | "What aren't we checking?", "audit coverage", "audit the harness" | The person | `references/mode-audit-coverage.md` |
| audit-weak-checks | "Are our checks fake?", "audit weak checks" | The person | `references/mode-audit-weak-checks.md` |
| verify-pr | A teammate's pull request | The person | `references/mode-verify-pr.md` |

Verify delegates missing proof to add-checks within the agreed scope, and add-checks loads add-tools for each probe or action a check needs; an existing-checks-only request keeps verify from building. "Audit the harness" with nothing more is coverage first, since weak checks hold checks to a map coverage keeps current; ask before running both. The weak-checks audit and verify-pr also work on a harness this framework didn't build, such as a repo's own folder of smoke checks, so neither waits for setup; every other mode needs a harness vf built, and with none, or one whose setup stopped, setup comes first and the original request becomes the offered next step. With no match, two equally good matches, or a question about the framework itself, list the modes one line each and ask which, recommending the one the repo's state points to.

Done when one mode is chosen, or the person has been asked.

## 2. Say what will run

When the mode does what the person asked, say it in one line, such as `Running explain: you asked how far to trust the checkout checks.`, and continue. When the job needs a mode only the person starts and they did not ask for it by name, such as setup in a repo with no harness before the verification they asked for, show the steps and end with `Needs you:` as `references/messages.md` describes, then wait: build nothing and start nothing until they say yes.

Done when the person knows what runs and has approved anything beyond their request.

## 3. Run the mode

Read the mode's file in full and follow every step; paths inside it are relative to this skill's folder. Read only the chosen mode's file and the references it names; a mode that hands off to another reads that one when it gets there. When a mode finishes, offer the natural next step in one line, such as add-checks for a feature the person names after setup, or the weak-checks audit after explain names checks never seen failing, and run it only on a yes.

Done when the mode's procedure reached its last step or stopped with the reason it gives, and any next step has been offered.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Run a mode only from its file, read in full during this run, never from memory of what it says.
- Outside a mode's steps, build no checks, start no app, and edit no harness file.

Reply: the mode's own reply, then at most one line offering the next step.
