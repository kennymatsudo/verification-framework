---
name: verification-framework
description: >-
  Start here when you don't know which verification skill you need. Takes any
  request about proving an app works, looks at what the repo already has, picks a
  playbook, and runs the framework's skills in order. Use for "set this repo up
  for verification", "did my change work?", "are our checks fake?", "check this
  teammate's PR", "what can this framework do?". Call a skill directly when you
  already know its name.
disable-model-invocation: true
---

# Verification framework

You own getting the person from a plain request to the right framework skill, run in the right order. You pick and hand over; the skills you load do the work and ask their own questions.

## 1. Look at the repo

Run `python3 <this skill's directory>/scripts/locate.py`. Its `--help` describes the output. For each harness it lists, run `<harness>/scripts/check.py` and note whether it stops on incomplete setup. With several harnesses and a request that doesn't name the app, ask which.

Done when you know each skill's path or that it's missing, and whether the repo has no harness, a harness whose setup stopped, or a ready one.

## 2. Pick a playbook

Match the request to one playbook:

| Playbook | When | Steps |
| --- | --- | --- |
| Set up | "Set up verification", "resume setup" | setup-verification, then offer add-feature-checks for one feature the person names |
| Verify a change | "Did my change work?", "verify checkout" | The app's verify skill, `<harness>/SKILL.md`, which follows verify-change and sends missing checks to add-feature-checks |
| Add checks | "Add checks for search", "what should we check next?" | add-feature-checks |
| Verify a PR | A teammate's pull request | verify-pr |
| Trust | "Can I trust these checks?", "how is checkout checked?" | explain-harness, then offer audit-weak-checks if it names checks never seen failing |
| Upkeep | "What aren't we checking?", "are our checks fake?" | audit-coverage for what has no check or checks stale code, audit-weak-checks for checks that would pass anyway; run the one asked and offer the other |
| Find bugs | "Look for bugs", "run exploratory testing" | explore-bugs |

With no harness, or a harness whose setup stopped, the playbook is Set up whatever the request said, and the original request becomes the offered next step. With no match, two equally good matches, or a question about the framework itself, list the playbooks one line each and ask which, recommending the one the repo's state points to.

Done when one playbook is chosen, or the person has been asked.

## 3. Check its skills are installed

Every skill the playbook names needs a path from step 1. For each missing one, stop and give its install line: `npx skills add kennymatsudo/verification-framework -s <name>`, with `-g` when this skill sits under the home directory.

Done when every skill the playbook needs has a path, or you stopped with the install lines.

## 4. Say what will run

When the playbook does what the person asked, say it in one line, such as `Running explain-harness: you asked how far to trust the checkout checks.`, and continue. When it does something else first, such as setup before the verification they asked for, show the steps and end with `Needs you:` as the harness's Messages rules describe, then wait.

Done when the person knows what runs and has approved anything beyond their request.

## 5. Run each step

Read the step's `SKILL.md` in full and follow it as if the person had called it with their request. Read the file rather than calling the skill through the agent's skill tool: most of these skills refuse that tool so they never start unprompted, and the person's call to this skill is the request to run them. Paths inside a loaded skill are relative to its own folder. Pass on what step 1 found, such as the harness path and `check.py`'s output, so the skill doesn't redo it or ask again.

When a step finishes, offer the playbook's next step in one line, and run it only on a yes.

Done when the loaded skill's own steps are done or it stopped on a named blocker, and any next step has been offered.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Run a skill only from its file, read in full during this run, never from memory of what it says.
- Outside a loaded skill's steps, build no checks, start no app, and edit no harness file.

Reply: the loaded skill's own reply, then at most one line offering the playbook's next step.
