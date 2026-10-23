# ADR 0002: Three skills: one for people, one for agents, one that explains

Status: Accepted. 2026-10-21.

## Problem

Verification has several jobs: prove the environment is ready, build tools, build checks, run checks on a change, audit a harness, test a teammate's pull request, and say how far a pass can be trusted. One skill per job gave people six person-only names to choose between, and a plain request like "are our checks fake?" reached nothing unless the person already knew which name to type. A generated app skill that carried its own copy of the procedure meant every fix had to be repeated in every app. And bare names like `add-tools` clash with other skill collections once installed side by side.

The only split that changes behavior is who may start a skill: a person by name, or an agent on its own.

## Decision

- **Three skills.** vf is the one a person runs by name; its modes are the jobs that must never start unprompted: setup, audit (coverage or weak checks), and verify-pr. vf-verify is the one an agent may start for its own change; its modes are verify, add-checks, and add-tools, and verify delegates to add-checks, which delegates to add-tools, inside one skill. vf-explain is its own agent-invocable skill: it only reads, and the teammate who needs it doesn't know any skill's name.
- **Names.** Every name starts with `vf-`, so typing it lists the whole set and nothing clashes; vf, the skill a person starts from, is the prefix alone. After the prefix comes the verb of the job: verify, explain. A mode is named the same way. A new skill is added only for a new split in who may start it, never for a new job.
- **Modes keep their procedures whole.** Each mode's procedure is one file in the skill's `references/`, so a run reads one procedure. The skill body only picks the mode. vf runs its own modes by path and the other two skills by name; the person's call to vf is the permission for everything inside it.
- **Setup stops at readiness.** The setup mode creates or resumes a harness, proves its doctor on the real app, publishes the doctor as the first tool, and ends with zero feature coverage allowed. Building proof is add-checks' job.
- **The app entry point stays thin.** The generated `verify-<app>` skill names its harness and delegates to vf-verify by name, so the procedure lives once.
- **Ownership between modes.** add-tools owns probes and actions, which judge nothing and need no plan or break. add-checks owns what judges: feature files, checks, their review, and planned-break proof. verify owns a whole request: it previews scope, builds missing proof within the agreed scope, and records results; an existing-checks-only request prohibits building. Building a check never authorizes building the feature.
- **vf-explain asks five fixed questions** of every check: does it do what a user does, does it look at the result itself, has it been seen to catch a break, did it run on the code you care about, and can you see the proof. A script answers the last three from the harness; the agent reads the check's code for the first two.

## Options we passed on

- **One skill.** Setup, audits, and PR verification must never start on an agent's own judgment, and a skill is either agent-invocable or not.
- **Two skills, vf-explain folded into vf.** Unreachable by the teammate who asks "why should I trust this pass?".
- **One skill per job with a shared preamble.** The person still picks among six names, and the generated skill needs several installs.
- **Setup also builds checks.** Its name doesn't say so, and developers were surprised by the turn into proof building.
- **Verify builds missing checks without a preview.** A run would silently change its scope.
- **Rename the plugin instead of prefixing skills.** Fixes Claude Code only; a `skills` CLI install stays ungrouped.
- **The full procedure in each generated app skill.** Fixes end up with many copies.

## What changes

`skills/` holds vf, vf-verify, and vf-explain, each with `references/mode-<name>.md`; the generated skill template; AGENTS.md's naming and invocation rules; README; USAGE.md; `locate.py`; and the tests.
