# Working in verification-framework

## What we're building

A coding agent says "done, tests pass," and nobody can tell from the report whether the feature works: unit tests fake the database and the browser, a test that can never fail still passes, and nothing names the version tested. This repo is the answer to that, in the form an engineer would recognize: a **test bench** built around the running app.

A bench has three parts, and so does every harness this framework builds:

- **Instruments** that drive and read the app from outside: probes that read its data, actions that do what a user or operator does, a doctor that reports what's running, and checks that drive one behavior and read back the result from storage, the response, or the screen, never through the app's own code. They're ordinary command-line programs in the app's language, so an engineer can use them by hand.
- **Calibration**: a check must fail on a planned break, the behavior broken on purpose in a scratch copy, before its passes count. A check edited since its break is uncalibrated again.
- **A notebook**: every run leaves a record with the exact commit in every repo, and a script computes each behavior's verdict from those records. An agent can lower a verdict with a reason but can never write Verified.

The agent builds the bench with a person in the loop. It takes expected behavior from requirements or the person, never from the code; previews what each check will prove and won't before building it; and has a separate agent review the check against that agreement. Then it uses the bench to verify its own change before it reports done. So the framework is as much a way to generate tests you can trust as a way to run them; the skills are the procedure that makes the generated tests trustworthy, and the script is what the agent can't talk its way past.

The skills use the [Agent Skills](https://agentskills.io) format and are published through the `skills` CLI and as a Claude Code plugin marketplace. Each harness is a **verification harness** folder in the app's repo. The README has the install commands and the skills index; USAGE.md describes how the skills behave; `docs/architecture.md` says where a change belongs.

Three skills ([ADR 0002](docs/adr/0002-three-skills.md)):

| Skill | Started by | Modes |
| --- | --- | --- |
| vf | A person, by name | setup (creates a harness and proves readiness), audit (coverage, or weak checks), verify-pr (tests a teammate's pull request) |
| vf-verify | An agent, for its own change | verify (runs the procedure and delegates missing proof to add-checks within scope), add-checks (builds and proves feature checks), add-tools (builds and proves probes and actions) |
| vf-explain | Anyone | Reads a harness and says how far to trust it |

The generated `verify-<app>` skill supplies scope and harness location. The weak-checks audit and verify-pr also work on a harness built without this framework.

## What every change must preserve

A pass from a harness is trustworthy: it ran on the real app, on a known version, through a calibrated check, with a record anyone can rerun or inspect. Every harness shares the same contract for what a pass means, the same evidence format, and the same report words; each app supplies only how it starts, how it's driven, and how its state is read. When a change would weaken any of these, don't make it.

Three things follow for every change, and each is a reason to say no to a feature that doesn't fit them:

- The instruments read the device, not its self-report. Nothing a check or probe judges by goes through the app's own models or logic.
- A person decides what gets measured. Expected behavior comes from requirements or the person, never from the code, and nothing is built before the person has seen what it will prove.
- The agent is not the judge of its own work. Verdicts are computed, a separate agent reviews each new check, and anything with a real or shared side effect waits for the person.

## How to weigh a design change

- **Reference, not blueprint.** A project used to test the framework is evidence about that case, not a required design. Put only the shared trust contract in the framework; keep project mechanics in that project's settings and tools.
- **General, with a fixed shape.** The framework must fit setups we haven't seen: one repo or several, any language, any layout. Generalize by finding out what the project already has, not by adding options. Every harness keeps maps, results, tools, and evidence in one fixed layout, so a run is repeatable and anyone can read it.
- **Developer experience.** For every change, say what the person running the skill sees and does: what they're asked, what they confirm, and what happens when something is wrong. Ask only what the project can't answer. Prefer a clear failure on the first run to a silent wrong result later.
- **Proof and tools.** Before building or running proof, preview what will be proven, what the check will do and read, and what it won't prove. Ask when the requirements leave expected behavior open rather than inferring it. Have a separate agent review each new check against the agreed plan, and keep the record of the run where the check failed on a planned break. Publish reusable CLI tools with one guide, `--help`, and enforced permissions; link the guide from project agent instructions only with permission.
- **User experience.** Results are read by people who didn't run them. Write reports in terms of what a user would notice, with the same words across skills. A reader skims a long message and approves it unread, so keep every message short and put the one decision on its last line.
- **Simple first.** Before adding a branch, option, file, or label, try making the new case a special case of an existing one (an app in one repo is the single-repo case of an app spread across several). Count the cost to every skill that reads a harness. When two designs keep the same trust, pick the one with fewer branches.
- **Who judges.** The main agent synthesizes and judges, on whatever model the user chose. Subagents gather evidence on a mid-tier model. Don't add a separate stronger synthesizer.

## Design records

- `docs/architecture.md` describes how the skills, the contract, and a harness fit together. Update it in place when a decision changes that structure.
- `docs/design.md` holds open questions, parked ideas, and the list of decisions. When a question is settled, remove it and link its ADR; drop a parked idea once it's picked up or rejected.
- Write an ADR only for a large or hard-to-reverse decision: one that changes the shared contract or what a pass means, adds or removes a skill, moves a job between skills, or changes what every harness contains. Record a smaller decision where it takes effect and in the commit message. A rejected proposal, a wording change, or a change inside one skill gets no ADR. When unsure, ask.
- An ADR lives in `docs/adr/`, numbered `NNNN-<slug>.md`, with four sections: Problem, Decision, Options we passed on, and What changes. Don't rewrite an accepted ADR; a reversal is a new ADR that names the one it replaces, and the old one's status says so.
- Write architecture.md, design.md, and every ADR for someone new to the project. Plain words; a framework term only when it's in the [USAGE.md glossary](USAGE.md#glossary), explained in passing if it's not obvious. Lead with the point. One line per passed-on option. An ADR fits on one screen.
- A decision every contributor must follow also goes into this file, a skill, or the README.

## Writing the docs

- **The problem to lead with.** The README and USAGE open with the moment the framework is for, an agent reporting done with nothing behind it, and only then say what the framework does.
- **The analogy and the fixed terms.** "Test bench", "instrument", "calibration", and "notebook" are the words that explain the idea. "Check", "probe", "action", "doctor", "planned break", and "evidence file" are the fixed terms in `rules.md`, the skills, and `vf.py`. Use the bench words to introduce and group; never put them in a command, a file name, or a rule.

## Repo rules

- One folder per skill: `skills/<name>/SKILL.md`, with `references/` for material only some branches read and `scripts/` for deterministic checks. The plugin auto-discovers skills, so no manifest edits.
- Practice-repo runs (`dogfood/`, `docs/dogfood.md`) and pilot notes (`.local/pilots/`) stay local and gitignored. Tracked files never link to them; describe a finding from them in the tracked doc itself.
- Skills stand alone. No paths into other repos, the author's machine, or another skill collection's files.
- Write for every agent (Claude Code, Codex, Cursor, and others): say "spawn a subagent", not a tool name, and name a model tier ("mid-tier"), not a model.
- Name the kind of tool a skill needs (ticket tracker, chat, code host), never the product. Have the skill list the session's tools, match each by what it can search, and report a kind with no tool as unsearched, not empty.

## Skill conventions

- **Name.** Every name starts with `vf-`, so typing it lists the whole set and avoids clashes; the one exception is vf, the skill a person starts from. After the prefix, a skill is named for the verb of its job, and so is a mode: setup, audit, verify-pr, verify, add-checks, add-tools. A new skill is added only for a new split between who may start it, not for a new job ([ADR 0002](docs/adr/0002-three-skills.md)).
- **Invocation.** vf runs only when called: `disable-model-invocation: true` in the frontmatter and `allow_implicit_invocation: false` in `agents/openai.yaml`. The generated `verify-<app>` entry point and vf-verify allow agent invocation so an agent can verify its own change. vf-explain allows it too, because it only reads and the teammate who needs it doesn't know its name. Keep the generated entry point thin: commands stay in settings and the procedure stays in vf-verify's verify mode.
- **Description.** Say what the skill does, give a few example requests that should trigger it, and end by pointing to the sibling skill for nearby jobs ("Use X to ...").
- **Body.** Open with what the skill owns ("You own ..."). Use numbered steps, each ending with a checkable "Done when" line. Close with Guardrails and a `Reply:` line that says what the final report contains, in the shape `references/messages.md` gives ([ADR 0003](docs/adr/0003-agree-on-proof-and-end-with-one-short-ask.md)); vf and vf-verify each carry an identical copy, and `tests/test_preamble.py` checks they match. A skill with modes keeps each mode's procedure in `references/mode-<name>.md`, opening with "Follow this when <skill> runs in <mode> mode" and keeping its own guardrails under "Guardrails for this mode"; the skill body only picks the mode and points at the file.
- **Guardrails.** Every skill's Guardrails open with the same four lines, word for word: change product code only in a scratch git worktree, removed afterward; drive and stop only app instances the run started or the user named, by process ID; ask before committing, pushing, posting, filing, or running anything with a real or shared side effect; never forge an event the real system would produce, and never loosen a check to turn a run green. `tests/test_guardrails.py` holds the exact wording.
- **Finding the harness.** Every skill that reads a harness finds it and gates on `vf.py validate` with the same two sentences, word for word; `tests/test_preamble.py` holds them. A skill that also works on a harness this framework didn't build carries only the gate sentence.
- **Other skills by name.** A skill points to another skill by its name, never by file path. A mode of the same skill is read by its path under `references/`.

## One shared contract

- The contract every harness follows is vf's `references/rules.md`, which includes the evidence format, and the `settings.md` template. A skill that reads a harness follows the harness's copy and doesn't restate it. A skill that also works on a harness this framework didn't create carries only the rules it needs there.
- Skills find a harness by `verify-*/rules.md` in the skills directories of the current folder and each folder above it, up to the repo's top level. Keep that marker stable. The folder holding that skills directory is the project root: recipes run from it and settings resolve from it ([ADR 0001](docs/adr/0001-one-harness-per-app.md)).
- A harness owns `README.md`, `recordings.html`, `features/`, `status.md`, `notes.md`, `tools.md`, `scripts/` (with `scripts/framework/`), and `evidence/` inside its directory. Settings configure mechanics, not artifact locations. Leave Git tracking and evidence retention to the team; don't edit Git ignore files.
- Setup ends at proven readiness with zero feature coverage allowed. Missing proof is built only within the agreed scope, and an explicit existing-checks-only request prohibits building. When a question about expected behavior, a missing permission, or a much larger scope comes up, the work that depends on it pauses while unrelated work continues.
- Every harness gets `rules.md` copied unchanged; anything that applies to one app goes in the `settings.md` template as a blank to fill in.
- When the contract changes, update `rules.md`, the `settings.md` template, `validate.py`, USAGE.md, and `docs/internals.md` together. Raise the `Rules version` line in `rules.md` when a change alters what a harness must do, so `sync` can refuse a downgrade; nothing in `validate.py` tracks it. `vf.py sync` records the hash of every file it copies in `scripts/framework/framework.sha256` and refuses to overwrite a copy that no longer matches; `validate.py` fails a `rules.md` that no longer matches ([ADR 0006](docs/adr/0006-one-versioned-tool-writes-every-record.md)). A change to any framework script's formats or output also updates `docs/internals.md`. vf-verify's verify mode reads only the `rules.md` sections it names, so a renamed, added, or split section updates its list too.
- What makes a probe or action trustworthy is stated once, in the Tool discovery, Probes, and Actions sections of `rules.md`. A skill that builds, reviews, or audits a tool points at those sections. The one exception is the weak-checks rubric, which must judge a harness that has no `rules.md`: it repeats the sentence word for word, and `tests/test_rubric.py` holds the shared sentences.
- Skills and `validate.py` support only the current harness format. A contract change carries no compatibility for earlier harnesses ([ADR 0001](docs/adr/0001-one-harness-per-app.md)).
- Report each behavior (a sub-feature in the feature map) only as Verified, Failed, or Not verified, as `rules.md` defines. `vf.py status` computes those verdicts from the evidence and writes `status.md`; no skill writes a Verified line, and an agent lowers a result only through `vf.py not-verified` ([ADR 0004](docs/adr/0004-judge-from-outside-and-compute-verdicts-from-evidence.md)). No check writes its own evidence file, and nothing writes a `Break-tested` line anywhere but `status.md`: `vf.py run` runs the doctor (the harness's readiness command), builds the record from the events a check reports, and fingerprints the harness's own code; `vf.py break run` logs the break in `evidence/breaks.jsonl`; `vf.py status` computes Break-tested from the evidence ([ADR 0006](docs/adr/0006-one-versioned-tool-writes-every-record.md)). A skill's own sorting labels stay inside that skill.

## Scripts

- Framework scripts use Python 3 standard library only. Generated app tools use the project's language, drivers, and connection settings; reads that judge state never go through the app's own models or logic.
- Exit codes: 0 means OK, 1 means it found a problem, 2 means it couldn't run.
- Unit tests live in `tests/test_<script>.py`, not beside the script, so an install ships no tests. Each names its script's folder as `SCRIPTS`. Run everything with `python3 -m unittest discover -s tests`.

## Creating or changing a skill

- **Validate.** Run `npx skills add . --list`, and `claude plugin validate .` if the Claude Code CLI is installed.
- **Docs.** Add or update the skill's row in the README's skills index, and update USAGE.md wherever it describes the skill's behavior.
