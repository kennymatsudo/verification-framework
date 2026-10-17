# Design

Open questions, parked ideas, and accepted decisions for the verification framework. Each decision is an ADR in [`adr/`](adr/), a short record of the problem, the decision, and the options passed on. See [architecture.md](architecture.md) for how the skills, the shared contract, and a harness fit together today.

## Weigh reference projects

A reference project can reveal a missing shared rule or an integration gap, but its layout, commands, and coverage stay local to that project. Recheck it at the version named by each result. Test portability on a different project shape before treating an approach as general.

[Research on AI agents and verification](../research/ai-verification.md) collects the published evidence behind the contract's rules, with sources.

## Open questions

### Add independent judges where an agent grades its own work

The skills already brief independent judges well. The check reviewer, audit-weak-checks' verifiers, and explore-bugs' refuter and calibration planter get the artifact and the original sources, never the author's reasoning, and are asked to find what's wrong. Two moments still let the author judge itself:

- The agent that wrote a check picks its planned break, so it can pick one the check is sure to catch. A fresh agent that hasn't seen the check could pick the break from the behavior and the code, as explore-bugs' planter does. Test this first on practice repos. Checks that catch their own planned breaks but miss the hidden ones show the author's breaks were too easy.
- An agent changes a check's expectation after it fails. In the pilot, the check reviewer ran once before the first run. When a later failure led the agent to change what the group step expects, no reviewer ran, because `rules.md` doesn't say a changed expectation counts as a materially changed check. Saying so would send the failing evidence and the sources to a fresh reviewer.

Each adds a subagent to every check built, so measure the first before adding it. If both land, write the judge briefing once in `rules.md`.

### Flag harness edits made during a run

An agent facing a failing check can loosen the check instead of fixing the code, and models attempt this far more often when a task can't be finished honestly. Proposed: verify-change records the harness's state when a run starts. If any harness file changed outside add-feature-checks, the report opens with "harness edited during this run" and the diff.

A fuller defense runs checks from a trusted copy and replays the saved planned break when a check changes, as mutation-testing tools like PIT do. It waits until this flag fires in practice.

### Ask for the requirements source when setup can't find it

audit-coverage's requirements pass runs only when `settings.md` names a requirements source, and nobody is asked for one. Setup's discovery subagent looks and writes `none` when it finds nothing, which is likely when requirements live in a doc or ticket outside the repo. The pass is then skipped on every run. Proposed:

- Setup asks one question when discovery finds nothing: where this app's requirements live, as a link, a file, or none. Only the team knows this, so it meets the "ask only what the project can't answer" bar.
- audit-coverage accepts a link or pasted list for one run, so a user can supply requirements without editing `settings.md`, and offers to save the link.
- A source the session has no tool to open is reported as unread, never treated as empty, matching how skills report a kind of tool with no tool as unsearched.

This changes `settings.md` guidance and setup's questions, so it touches the contract files together. Test the setup question on a practice repo whose requirements sit outside the repo.

### Test the code layout and the moved formats

[ADR 0011](adr/0011-put-each-format-where-its-readers-look.md) moves the feature-map format into `rules.md` and a recommended code layout, drawn from a single Python harness, into add-feature-checks, so add-feature-checks no longer loads setup-verification. Accept it once a TypeScript harness has been built with the layout and it fit without forcing, and a build run in a fresh session never loads setup.

### Test recorded runs on a second app

[ADR 0012](adr/0012-record-runs-and-replay-them-from-evidence.md) proposes recording every check that drives a screen, with a shared replay page and clip tool, drawn from one Python browser harness. Accept it once a harness in another language records a run that replays and cuts cleanly, captions included.

## Decisions

ADRs 0011 and 0012 are proposed and wait on the tests under Open questions. The rest are accepted:

- [0001: One harness per app, in a fixed layout, covering every repo it runs on](adr/0001-one-harness-per-app.md)
- [0002: Setup proves readiness and resumes from the harness](adr/0002-setup-proves-readiness-and-resumes.md)
- [0003: Each skill owns one part of verification](adr/0003-each-skill-owns-one-part-of-verification.md)
- [0004: Agree on proof and publish reusable tools](adr/0004-agree-on-proof-and-publish-reusable-tools.md)
- [0005: Drive through the app, judge from outside it](adr/0005-judge-from-outside-the-app.md)
- [0006: Back every Verified with its evidence](adr/0006-back-every-verified-with-its-evidence.md)
- [0007: Messages end with one short ask](adr/0007-messages-end-with-one-short-ask.md)
- [0008: Name skills by a verb, then the question they answer](adr/0008-name-skills-by-verb-and-question.md)
- [0009: Explain why to trust the harness](adr/0009-explain-why-to-trust-the-harness.md)
- [0010: A starting skill that runs the others](adr/0010-a-starting-skill-that-runs-the-others.md)

## Parked ideas

### Add a test-first playbook

Test-first means writing the check before the code it checks. A verification-framework playbook ([ADR 0010](adr/0010-a-starting-skill-that-runs-the-others.md)) could run add-feature-checks from the requirements before the feature exists, record the checks as wanted but not built, and hand back so the feature gets built in the normal session. It then reruns them with the app's verify skill.

The run before the feature exists works like a planned break, since it's the app with the behavior absent. Check whether `check.py` accepts a break run on the base commit rather than a scratch copy. That run fails every step for one reason, the missing page or endpoint, so a claim about values, such as a total, still needs a planned break after the build.

Checks written before the code can't be shaped to fit it, which helps with independent judges above. The playbook never writes the feature, so the shared guardrails stay as they are.

### Hide verify-change from the slash menu

The app's verify skill would then be the one way a person starts verification. Agents still call verify-change. Claude Code supports this in frontmatter. Other agents are unchecked.

### Script the harness copy and upgrade

Setup copies `rules.md` and four scripts unchanged and fills two templates, the same way every run. A setup script that does this would guarantee "unchanged" and shorten setup's step 2.

Nothing updates a harness when the framework changes. The pilot was updated by hand. Setup, run on an existing harness, could reuse the same script to refresh `rules.md`, the shared scripts, and the generated verify skill.
