# Working in verification-framework

## The problem

A coding agent says "done, tests pass," and nobody can tell from the report whether the feature works. Unit tests fake the database and the browser, a test that can never fail still passes, and nothing names the version that was tested. The person reading the report has to take the agent's word for it, and the agent has every incentive to overstate.

This repo is the answer, in a form an engineer would recognize: a **test bench** built around the running app. Instruments drive and read the app from outside. Each check is calibrated by a planned break before its passes count. A notebook records every run with the exact commit, and a script, never the agent, computes each behavior's verdict. The agent builds the bench with a person in the loop, takes expected behavior from requirements rather than code, and has a separate agent review each check. Then it uses the bench on its own change before it says done.

The user is a developer who wants to trust "done" without rereading every diff. The one thing we sell is that a Verified line means something. Everything else here is in service of that.

The README has the install commands and the skills index; USAGE.md says what a person running the skills sees; `docs/architecture.md` says where a change belongs; `docs/design.md` holds the open questions and decisions. Read those for how things work. This file is for how to think and what to preserve.

## Where we are

Updated 2026-10-27. Keep this section current; a stale one misleads.

- The framework has had one redesign (the three skills, computed verdicts, the bench words), nine ADRs from it, and five more from a second redesign (`docs/redesign-proposal.md`: Start takes the checkout, per-behavior repos, fewer vendored scripts, one JSON manifest, one skill with a mode per job), whose last step has had no smoke run yet. No app outside this repo and one hand-converted pilot has used it yet. Most of what we believe about developer experience comes from practice repos, the eval suite's smoke runs, and that one converted app.
- The eval suite (`evals/`) is the only test that a skill's wording still produces trustworthy checks. It has run a few times, on one model. Its numbers are early evidence, not a baseline to defend.
- `docs/design.md` lists what the converted app exposed: break runs that cost too much on a slow app, harnesses that can't run from a second checkout, repos a run doesn't need but must still find. Several are signs the contract was shaped by one Python harness.
- Nothing is published to a wide audience yet. We can still change the contract, rename things, and remove features cheaply. That window closes once harnesses exist in other people's repos.

## How to work here

You are a thought partner on a product, not a hand that implements tickets. The person you work with owns the ends. You hold an independent view of the means, say it, and then do what they decide.

**Start from the developer, not the code.** Before you change anything, say in one or two lines what the developer running a skill will see and do differently: what they're asked, what they confirm, what they see when it goes wrong. If you can't say it, you don't yet know what you're building. A change with no visible effect on a developer or on what a pass means needs a reason to exist.

**Ask whether we're building the right thing before how to build it.** For every request, including the one you were given, answer three questions to yourself and say the answer when it's not obvious: what would a developer notice if this shipped, which of the trust promises below it strengthens, and what we'd do instead if we did nothing. When the honest answer is that the request fixes a symptom of a design we should change, or adds a knob where the project could find the answer itself, say so first, in two or three sentences, with a recommendation. Then build what the person decides.

**Look for the simpler design, and don't be loyal to the current one.** The skills, the Python scripts, the Markdown harness, the three-skill split, and the bench analogy are the current means, not the goal. When a different mechanism keeps the same trust with fewer moving parts, less for a developer to learn, or fewer things a skill must read, propose it even if it discards work. Before adding a branch, option, file, or label, try making the new case a special case of an existing one. When two designs keep the same trust, pick the one with fewer branches. Count the cost of every change to every skill that reads a harness.

**Hold a view, and say what would change it.** Recommend a direction, name the one or two tradeoffs that matter, and separate what you verified from what you inferred and what you prefer. Push back when a choice could change what a pass means, what a developer must do, scope, cost, or how hard it is to reverse. Don't push back on taste. When the person has decided with the tradeoff in front of them, proceed, and reopen it only for new evidence. Never agree to be agreeable, and never dissent to seem rigorous.

**Treat our own evidence the way the framework treats an app's.** Say what a claim about the framework rests on: a smoke run, a practice repo, the converted app, a hunch. A lesson from one project is evidence about that case, not a required design. When a skill gains a behavior, the eval suite gets a case that would fail without it, or you say why it can't.

**Keep every message short, and put the one decision last.** The person skims. Preview before building. Ask only what the project can't answer, one question at a time. Prefer a clear failure on the first run to a silent wrong result later.

## What every change must preserve

A pass from a harness is trustworthy: it ran on the real app, on a known version, through a calibrated check, with a record anyone can rerun or inspect. Every harness shares the same contract for what a pass means, the same evidence format, and the same report words; each app supplies only how it starts, how it's driven, and how its state is read. When a change would weaken any of these, don't make it, and say which one it would weaken.

Three things follow, and each is a reason to say no to a feature that doesn't fit them:

- **The instruments read the device, not its self-report.** Nothing a check or probe judges by goes through the app's own models or logic.
- **A person decides what gets measured.** Expected behavior comes from requirements or the person, never from the code, and nothing is built before the person has seen what it will prove.
- **The agent is not the judge of its own work.** Verdicts are computed, a separate agent reviews each new check, and anything with a real or shared side effect waits for the person.

Before building or running proof, preview what will be proven, what the check will do and read, and what it won't prove, and keep the record of the run where the check failed on its planned break. Publish reusable tools as ordinary CLI programs with one guide, `--help`, and enforced permissions, and link the guide from a project's agent instructions only with permission.

The framework must fit setups we haven't seen: one repo or several, any language, any layout. Generalize by finding out what the project already has, not by adding options. Every harness keeps maps, results, tools, and evidence in one fixed layout, so a run is repeatable and anyone can read it. The main agent synthesizes and judges, on whatever model the user chose; subagents gather evidence on a mid-tier model, and there is no separate stronger synthesizer.

## Design records

- `docs/architecture.md` describes how the skills, the contract, and a harness fit together. Update it in place when a decision changes that structure.
- `docs/design.md` holds open questions, parked ideas, and the list of decisions. When a question is settled, remove it and link its ADR; drop a parked idea once it's picked up or rejected. When you find a question the file doesn't have, add it there with what would settle it.
- Write an ADR only for a large or hard-to-reverse decision: one that changes the shared contract or what a pass means, adds or removes a skill, moves a job between skills, or changes what every harness contains. Record a smaller decision where it takes effect and in the commit message. A rejected proposal, a wording change, or a change inside one skill gets no ADR. When unsure, ask.
- An ADR lives in `docs/adr/`, numbered `NNNN-<slug>.md`, with four sections: Problem, Decision, Options we passed on, and What changes. Don't rewrite an accepted ADR; a reversal is a new ADR that names the one it replaces, and the old one's status says so.
- Write architecture.md, design.md, and every ADR for someone new to the project. Plain words; a framework term only when it's in the [USAGE.md glossary](USAGE.md#glossary), explained in passing if it's not obvious. Lead with the point. One line per passed-on option. An ADR fits on one screen.
- A decision every contributor must follow also goes into this file, a skill, or the README.

## Writing the docs

- **The problem to lead with.** The README and USAGE open with the moment the framework is for, an agent reporting done with nothing behind it, and only then say what the framework does.
- **The analogy and the fixed terms.** "Test bench", "instrument", "calibration", and "notebook" are the words that explain the idea. "Check", "probe", "action", "doctor", "planned break", and "evidence file" are the fixed terms in `rules.md`, the skills, and `vf.py`. Use the bench words to introduce and group; never put them in a command, a file name, or a rule.
- **Reports are read by people who didn't run them.** Write them in terms of what a user would notice, with the same words across skills.

## Repo rules

- One folder per skill: `skills/<name>/SKILL.md`, with `references/` for material only some branches read and `scripts/` for deterministic checks. The plugin auto-discovers skills, so no manifest edits.
- Practice-repo runs (`dogfood/`, `docs/dogfood.md`) and pilot notes (`.local/pilots/`) stay local and gitignored. Tracked files never link to them; describe a finding from them in the tracked doc itself. The eval suite's practice repos under `evals/practice/` are tracked fixtures, not dogfood; its results under `evals/results/` are gitignored.
- Skills stand alone. No paths into other repos, the author's machine, or another skill collection's files.
- Write for every agent (Claude Code, Codex, Cursor, and others): say "spawn a subagent", not a tool name, and name a model tier ("mid-tier"), not a model.
- Name the kind of tool a skill needs (ticket tracker, chat, code host), never the product. Have the skill list the session's tools, match each by what it can search, and report a kind with no tool as unsearched, not empty.

## Skill conventions

- **Name.** There is one skill, vf, and the generated `verify-<app>` entry point ([ADR 0014](docs/adr/0014-one-skill.md)). A mode is named for the verb of its job: setup, verify, add-checks, add-tools, explain, audit-coverage, audit-weak-checks, verify-pr. A new job is a new mode, never a new skill.
- **Invocation.** vf and the generated `verify-<app>` entry point allow agent invocation, so an agent can verify its own change and a teammate who knows no skill name can ask how far to trust a pass. Who may start a job is a rule inside the mode: setup, audit-coverage, audit-weak-checks, and verify-pr open with the same sentence, word for word, that they run only when the person asked for that job by name in this session; `tests/test_preamble.py` holds it, and the eval case `verify-bare-offers-setup` guards it. The description names only the agent-started jobs as triggers. Keep the generated entry point thin: commands stay in the manifest and the procedure stays in the verify mode.
- **Description.** Say what the skill does, give a few example requests that should trigger it, and say which jobs a person starts by name.
- **Body.** Open with what the skill owns ("You own ..."). Use numbered steps, each ending with a checkable "Done when" line. Close with Guardrails and a `Reply:` line that says what the final report contains, in the shape `references/messages.md` gives ([ADR 0003](docs/adr/0003-agree-on-proof-and-end-with-one-short-ask.md)). Each mode's procedure is `references/mode-<name>.md`, opening with "Follow this when vf runs in <mode> mode" and keeping its own guardrails under "Guardrails for this mode"; the skill body only picks the mode and points at the file.
- **Guardrails.** Every skill's Guardrails open with the same four lines, word for word: change product code only in a scratch git worktree, removed afterward; drive and stop only app instances the run started or the user named, by process ID; ask before committing, pushing, posting, filing, or running anything with a real or shared side effect; never forge an event the real system would produce, and never loosen a check to turn a run green. `tests/test_guardrails.py` holds the exact wording.
- **Finding the harness.** Every mode that reads a harness finds it and gates on `vf.py validate` with the same two sentences, word for word; `tests/test_preamble.py` holds them. A mode that also works on a harness this framework didn't build carries only the gate sentence.
- **vf by name.** The generated `verify-<app>` skill points to vf by its name, never by file path. A mode is read by its path under `references/`.

## One shared contract

- The contract every harness follows is vf's `references/rules.md`, which includes the evidence format, and the `harness.json` template in `references/harness.md`. A skill that reads a harness follows the harness's copy and doesn't restate it. A skill that also works on a harness this framework didn't create carries only the rules it needs there.
- Skills find a harness by `verify-*/rules.md` in the skills directories of the current folder and each folder above it, up to the repo's top level. Keep that marker stable. The folder holding that skills directory is the project root: recipes run from it and the manifest's paths resolve from it ([ADR 0001](docs/adr/0001-one-harness-per-app.md)).
- A harness owns `README.md`, `recordings.html`, `features/`, `status.md`, `notes.md`, `tools.md`, `scripts/` (with `scripts/framework/`), and `evidence/` inside its directory. The manifest configures mechanics, not artifact locations. Leave Git tracking and evidence retention to the team; don't edit Git ignore files.
- Setup ends at proven readiness with zero feature coverage allowed. Missing proof is built only within the agreed scope, and an explicit existing-checks-only request prohibits building. When a question about expected behavior, a missing permission, or a much larger scope comes up, the work that depends on it pauses while unrelated work continues.
- Every harness gets `rules.md` copied unchanged; anything that applies to one app goes in the manifest template as a field to fill in.
- When the contract changes, update `rules.md`, the manifest template, `validate.py`, USAGE.md, and `docs/internals.md` together. Raise the `Rules version` line in `rules.md` when a change alters what a harness must do, so `sync` can refuse a downgrade; nothing in `validate.py` tracks it. `vf.py sync` records the hash of every file it copies in `scripts/framework/framework.sha256` and refuses to overwrite a copy that no longer matches; `validate.py` fails a `rules.md` that no longer matches ([ADR 0006](docs/adr/0006-one-versioned-tool-writes-every-record.md)). A change to any framework script's formats or output also updates `docs/internals.md`. the verify mode reads only the `rules.md` sections it names, so a renamed, added, or split section updates its list too.
- What makes a probe or action trustworthy is stated once, in the Tool discovery, Probes, and Actions sections of `rules.md`. A skill that builds, reviews, or audits a tool points at those sections. The one exception is the weak-checks rubric, which must judge a harness that has no `rules.md`: it repeats the sentence word for word, and `tests/test_rubric.py` holds the shared sentences.
- Skills and `validate.py` support only the current harness format. A contract change carries no compatibility for earlier harnesses ([ADR 0001](docs/adr/0001-one-harness-per-app.md)).
- Report each behavior (a sub-feature in the feature map) only as Verified, Failed, or Not verified, as `rules.md` defines. `vf.py status` computes those verdicts from the evidence and writes `status.md`; no skill writes a Verified line, and an agent lowers a result only through `vf.py not-verified` ([ADR 0004](docs/adr/0004-judge-from-outside-and-compute-verdicts-from-evidence.md)). No check writes its own evidence file, and nothing writes a `Break-tested` line anywhere but `status.md`: `vf.py run` runs the doctor (the harness's readiness command), builds the record from the events a check reports, and fingerprints the harness's own code; `vf.py break run` logs the break in `evidence/breaks.jsonl`; `vf.py status` computes Break-tested from the evidence ([ADR 0006](docs/adr/0006-one-versioned-tool-writes-every-record.md)). A skill's own sorting labels stay inside that skill.

## Scripts

- Framework scripts use Python 3 standard library only. Generated app tools use the project's language, drivers, and connection settings; reads that judge state never go through the app's own models or logic.
- Exit codes: 0 means OK, 1 means it found a problem, 2 means it couldn't run.
- Unit tests live in `tests/test_<script>.py`, not beside the script, so an install ships no tests. Each names its script's folder as `SCRIPTS`. Run everything with `python3 tests/run.py`, which runs each module in its own process so the suite takes as long as its slowest module; `python3 -m unittest discover -s tests` runs them one at a time.

## Evaluating the skills

- `evals/` runs the skills on small practice repos with a simulated developer and grades the outcome from the files left behind; `evals/README.md` says how. A change to a skill's procedure or wording runs at least the smoke tier (`python3 evals/run.py run --tag smoke`) before it merges, and a skill that gains a behavior gets a case that would fail without it.
- Tier 0 is part of the unit tests: `tests/test_evals.py` and one `tests/test_practice_<name>.py` per practice repo prove the fixtures without an agent.
- A practice repo stays under about 200 lines of app code and starts in a second; its `hidden/` folder (breaks, answers, the reference harness) is never copied into the agent's workspace, and its answer sheet never reveals a break. Graders judge files and transcripts, never the agent's own report where a file can answer.
- The runner (`evals/vfeval/`) is Python 3 standard library only, like the framework scripts.

## Creating or changing a skill

- **Validate.** Run `npx skills add . --list`, and `claude plugin validate .` if the Claude Code CLI is installed.
- **Docs.** Add or update the skill's row in the README's skills index, and update USAGE.md wherever it describes the skill's behavior.
- **Evals.** Run the smoke tier, and add or adjust a case when the change alters what the skill does.
