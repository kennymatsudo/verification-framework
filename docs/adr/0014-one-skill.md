# ADR 0014: One skill, with a mode for each job

Status: Accepted. 2026-10-27. Fourth step of [the redesign](../redesign-proposal.md). Reverses the three-skill split of [ADR 0002](0002-three-skills.md); its other decisions stand.

## Problem

ADR 0002 split the jobs into three skills by who may start them, because a skill is either agent-invocable or not. The split rested on one flag, and everything else it needed was overhead: `locate.py` to find the sibling skills, a playbook table and an install-check step in vf, three copies per skills directory per agent, install lines in every skill, the same four guardrails and two gate sentences in three bodies, two copies of `messages.md` with a test keeping them equal, and three descriptions each pointing at the other two. The fourth smoke run made vf agent-invocable and found no run of eight that started setup, an audit, or PR verification unasked (evals/README.md, "Fourth run"). The flag was guarding against something the mode text already prevented.

## Decision

`vf` is the only framework skill, and an agent may invoke it. Its modes are the eight jobs: setup, verify, add-checks, add-tools, explain, audit-coverage, audit-weak-checks, and verify-pr, each a file under `references/`. The generated `verify-<app>` entry point stays as the everyday name and delegates to vf in verify mode.

- **Who may start a job is a sentence in the mode.** Setup, the two audits, and verify-pr open with the same sentence, word for word: run only when the person asked for this job by name in this session, otherwise offer it in one line and stop. `tests/test_preamble.py` holds the sentence, and the eval case `verify-bare-offers-setup` guards the behavior: an agent asked to verify in a repo with no harness must offer setup and build nothing.
- **The description names only the agent-started jobs as triggers**, and says the others are asked for by name, so an agent choosing a skill from its description is not invited to set up or audit.
- **One committed copy.** A harness's skills directory holds `vf/` alone. `locate.py` leaves the harness; the list of skills directories it held moves into `vf.py sync`. The Rules version rises to 7, since what every harness contains changes.
- **`trust_facts.py` stays.** ADR 0012 expected it to fold into `vf.py status` once the manifest removed its duplicate parsing. It now loads `validate.py`'s parser, so the duplication is gone and the fold would be a rename.
- **The tradeoff.** An agent could start setup or an audit on its own judgment. The exposure is cost and noise, not trust: every real or shared side effect still waits for the person, and verdicts are still computed. A smoke run in which an agent starts a person-only mode unasked would reopen this.

## Options we passed on

- **Keep three skills behind one merged description.** Keeps every cost above for a split one flag enforced.
- **Two skills, vf and vf-explain.** The teammate who asks "can I trust this?" reaches vf's explain mode by the same description; a second skill buys nothing.
- **Hide the person-only modes from agents in frontmatter.** Claude Code only; other agents would see them anyway.
- **Move the harness beside the code (the proposal's step 5).** Not trust-relevant and not taken; it stays a parked idea.

## What changes

`skills/vf/SKILL.md` (the mode table), `references/mode-explain.md` (from vf-explain's body), the vf-verify references moved into `skills/vf/references/`, `skills/vf/evals/triggers.json`, `vf.py` (`COMMITTED_SKILLS`, `SKILLS_DIRS`, `FRAMEWORK_SCRIPTS`), `rules.md` (version 7), the entry-point and README templates, `tests/test_preamble.py`, `test_vf.py`, `test_code_state.py`, the eval case prompts and reference harnesses, README, USAGE.md, `docs/architecture.md`, `docs/internals.md`, and AGENTS.md. `skills/vf-verify/`, `skills/vf-explain/`, `locate.py`, and `tests/test_locate.py` are removed. A harness updated with `sync` loses its `vf-verify/` and `vf-explain/` copies and `locate.py`.
