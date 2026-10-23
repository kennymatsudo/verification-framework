---
name: vf
description: >-
  Start here for anything a person runs by name about proving an app works: set
  up or update a verification harness, audit it, verify a teammate's pull
  request, or ask what the framework can do. Use for "set up verification for
  this app", "update the harness", "audit coverage", "are our checks fake?",
  "verify PR #123", "did my change work?". Use
  vf-verify to verify or build checks for your own change, and vf-explain to ask
  how far to trust a pass.
disable-model-invocation: true
---

# Verification framework

You own getting the person from a plain request to the right job, run in the right order. Four jobs are modes of this skill, run from its `references/`; two are skills of their own, vf-verify and vf-explain, which an agent may also start unasked.

## 1. Look at the repo

Run `python3 <this skill's directory>/scripts/locate.py`. Its `--help` describes the output. For each harness it lists, run `<harness>/scripts/framework/vf.py validate` and note whether it stops on incomplete setup. With several harnesses and a request that doesn't name the app, ask which. A harness whose `vf.py` is missing or doesn't know `validate` predates the installed framework; plan the update mode first.

Done when you know whether vf-verify and vf-explain are installed, and whether the repo has no harness, a harness whose setup stopped, or a ready one.

## 2. Pick a playbook

Match the request to one playbook:

| Playbook | When | Steps |
| --- | --- | --- |
| Set up | "Set up verification", "resume setup" | Setup mode, `references/mode-setup.md`, then offer vf-verify in add-checks mode for one feature the person names |
| Update | "Update the harness", "I updated the framework" | Setup mode, asked only to update, then offer it again to prove readiness |
| Verify a change | "Did my change work?", "verify checkout" | The app's verify skill, `<harness>/SKILL.md`, which hands off to vf-verify |
| Add checks | "Add checks for search", "what should we check next?" | vf-verify in add-checks mode |
| Add tools | "Add this script as a tool", "let agents look up an order" | vf-verify in add-tools mode |
| Verify a PR | A teammate's pull request | Verify-pr mode, `references/mode-verify-pr.md` |
| Trust | "Can I trust these checks?", "how is checkout checked?" | vf-explain, then offer the audit mode for weak checks if it names checks never seen failing |
| Audit | "What aren't we checking?", "are our checks fake?", "audit the harness" | Audit mode: `references/mode-audit-coverage.md` for what has no check or checks stale code, `references/mode-audit-weak-checks.md` for checks that would pass anyway. "What aren't we checking?" is coverage, "are our checks fake?" is weak checks; for both, recommend coverage first, since weak checks hold checks to a map coverage keeps current, and ask before running both |

With no harness, or a harness whose setup stopped, the playbook is Set up whatever the request said, and the original request becomes the offered next step. With no match, two equally good matches, or a question about the framework itself, list the playbooks one line each and ask which, recommending the one the repo's state points to.

Done when one playbook is chosen, or the person has been asked.

## 3. Check its skills are installed

A playbook that names vf-verify or vf-explain needs its path from step 1. For a missing one, stop and give its install line: `npx skills add kennymatsudo/verification-framework -s <name>`, with `-g` when this skill sits under the home directory.

Done when every skill the playbook needs has a path, or you stopped with the install lines.

## 4. Say what will run

When the playbook does what the person asked, say it in one line, such as `Running vf-explain: you asked how far to trust the checkout checks.`, and continue. When it does something else first, such as setup before the verification they asked for, show the steps and end with `Needs you:` as `references/messages.md` describes, then wait.

Done when the person knows what runs and has approved anything beyond their request.

## 5. Run each step

For a mode of this skill, read its `references/mode-<name>.md` in full and follow it as if the person had asked for that job; paths inside it are relative to this skill's folder. For vf-verify or vf-explain, load the skill by name with the person's request and the mode it should run in. Pass on what step 1 found, such as the harness path and `vf.py validate`'s output, so no step redoes it or asks again.

When a step finishes, offer the playbook's next step in one line, and run it only on a yes.

Done when the step's own procedure is done or it stopped on a named blocker, and any next step has been offered.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Run a mode only from its file, read in full during this run, never from memory of what it says.
- Outside a mode's steps, build no checks, start no app, and edit no harness file.

Reply: the mode's or the loaded skill's own reply, then at most one line offering the playbook's next step.
