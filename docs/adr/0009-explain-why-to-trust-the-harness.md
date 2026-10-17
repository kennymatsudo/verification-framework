# ADR 0009: Explain why to trust the harness

Status: Accepted. 2026-10-16.

## Problem

A teammate who didn't build a harness sees "Verified" and has no quick way to know what it's worth. The answer is spread across feature files, `status.md`, `tools.md`, and saved runs, and the words that carry it, such as break-tested, only mean something to whoever built it. The audit skills judge and fix the harness; nothing explains it.

## Decision

Add explain-harness, a read-only skill that answers "how far can I trust this?" with the same five questions for every check:

1. Does it do what a user does?
2. Does it look at the result itself, rather than asking the app?
3. Have we seen it catch a problem, because someone broke the app on purpose and the check failed?
4. Did it run on the code you care about?
5. Can you see the proof?

These are the framework's existing promises (real entry point and outside reads, [ADR 0005](0005-judge-from-outside-the-app.md); planned break, recorded commit, and evidence, [ADR 0006](0006-back-every-verified-with-its-evidence.md)) in words a newcomer can follow, and they are the fixed wording for explaining trust.

- **One level at a time.** With no question, it walks one real check through the five questions, then tallies where trust is weakest, then offers two or three follow-ups naming this harness's behaviors. It asks nothing up front.
- **Facts from a script, judgment from code.** `trust_facts.py` reads questions 3 to 5 from what the harness records, using the harness's own `check.py` as the parser, and can write one HTML page to share. Questions 1 and 2 are free text in the feature files, so the agent reads the check's code and quotes the line.
- **The agent may start it.** Setup and audit skills run only when called by name. This one only reads, and the person who needs it, a teammate asking "why should I trust this pass?", doesn't know it exists.

## Options we passed on

- **Only a script.** It lists facts but can't answer the teammate's question or say what to ask next.
- **Fold it into the generated verify-\<app\> skill.** That skill stays thin.
- **Name it audit-trust.** An audit finds and fixes problems; this one changes nothing.
- **Make questions 1 and 2 required fields in feature files.** Sturdier, but a format change for every harness; revisit if quoted code proves hard to trust.
- **Plain wording in every skill's report now.** Wait to see whether it works for teammates here first.

## What changes

A new `skills/explain-harness/` with its script and a subagent prompt. AGENTS.md adds the `explain` verb and the invocation exception. README, USAGE, architecture, and internals describe the skill and the script's output. A change to the feature-file or `status.md` format also updates `trust_facts.py`.
