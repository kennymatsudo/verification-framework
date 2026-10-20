# Working in verification-framework

Agent skills in the [Agent Skills](https://agentskills.io) format for proving a change works on the running app, published through the `skills` CLI and as a Claude Code plugin marketplace. The skills set up, run, and maintain a verification harness in an app's repo: the tools, feature map, and checks an agent uses to prove a change works, and to report honestly when it can't. The README has the install commands and the skills index; USAGE.md describes how the skills behave.

setup-verification creates a harness and proves environment readiness. add-tools builds and proves probes and actions, before or apart from any check. add-feature-checks builds and proves feature checks, loading add-tools for the probes and actions they need. verify-change runs its verification procedure and delegates missing proof to add-feature-checks within the requested scope; the generated app skill supplies scope and harness location. audit-coverage, audit-weak-checks, explore-bugs, verify-pr, and explain-harness read a harness; audit-weak-checks and verify-pr also work on a harness built without this framework. verification-framework picks and runs the others for someone who doesn't know their names.

## What every change must preserve

A pass from a harness is trustworthy: it ran on the real app, on a known version, through a check that has been shown to fail, with evidence anyone can rerun or inspect. Every app's harness shares the same contract for what a pass means, the same evidence format, and the same report words; each app supplies only how it starts, how it's driven, and how its state is read. When a change would weaken any of these, don't make it.

## How to weigh a design change

- **Reference, not blueprint.** A project used to test the framework is evidence about that case, not a required design for other harnesses. Put only the shared trust contract in the framework; keep project mechanics in that project's settings and tools.
- **General, with a fixed shape.** The framework must fit setups we haven't seen: one repo or several, any language, any layout. Generalize by finding out what the project already has, not by adding options. Keep the contract and report words fixed; every harness keeps maps, results, tools, and evidence in one fixed internal layout, so a run is repeatable and anyone can read it.
- **Developer experience.** For every change, say what the person running the skill sees and does: what they're asked, what they confirm, and what happens when something is wrong. Ask only what the project can't answer. Prefer a clear failure on the first run to a silent wrong result later.
- **Proof and tools.** Preview behavior, real actions, observations, and exclusions before building or running proof. Confirm meaningful inferred acceptance conditions, independently review new checks against the agreed plan, and retain planned-break proof. Publish reusable CLI tools with one guide, --help, and enforced permissions; link the guide from project agent instructions only with permission.
- **User experience.** Results are read by people who didn't run them: reviewers, teammates, ticket owners. Write reports in terms of what a user would notice, and keep the same words across skills. A reader skims a long message and approves it unread, so keep every message short and put the one decision on its last line.
- **Simple first.** Before adding a branch, option, file, or label, try making the new case a special case of an existing one (one repo is a system with a single repo). Count the cost to every skill that reads a harness, not just the one you're editing. When two designs keep the same trust, pick the one with fewer branches.
- **Who judges.** The main agent synthesizes and judges, on whatever model the user chose. Subagents gather evidence on a mid-tier model. Don't add a separate stronger synthesizer.

## Design records

- `docs/architecture.md` describes how the skills, the shared contract, and a harness fit together, and where each kind of change goes. Update it in place when a decision changes that structure.
- `docs/design.md` holds what we're weighing, the open questions, and a list of decisions. Keep it current: when a question is settled, remove it and link its ADR if it has one; drop a parked idea once it's picked up or rejected.
- Write an ADR only for a large or hard-to-reverse decision: one that changes the shared contract or what a pass means, adds or removes a skill, moves a job between skills, or changes what every harness contains. Record a smaller decision where it takes effect, in the skill or doc it changes and the commit message. A rejected proposal, a wording change, or a change inside one skill gets no ADR. When unsure, ask before writing one.
- An ADR lives in `docs/adr/`, numbered `NNNN-<slug>.md`, with four sections: Problem, Decision, Options we passed on, and What changes. Don't rewrite an accepted ADR; a reversal is a new ADR that names the one it replaces, and the old one's status says so.
- Write both for someone new to the project. Use plain words; use a framework term only when it's in Terms below, and explain it in passing if it's not obvious. Lead with the point. Give each passed-on option one line on why. Cut anything the reader would accept without being told. An ADR should fit on one screen.
- A decision every contributor must follow also goes into this file, a skill, or the README.

## Terms

Use the [USAGE.md glossary](USAGE.md#glossary) for framework terminology.

## Repo rules

- One folder per skill: `skills/<name>/SKILL.md`, with `references/` for material only some branches read and `scripts/` for deterministic checks. The plugin auto-discovers skills, so no manifest edits.
- Practice-repo runs (`dogfood/`, `docs/dogfood.md`) and pilot notes (`.local/pilots/`) stay local and are gitignored. Tracked files never link to them; describe a finding from them in the tracked doc itself.
- Skills must stand alone. No paths into other repos, the author's machine, or another skill collection's setup files.
- Write for every agent (Claude Code, Codex, Cursor, and others): say "spawn a subagent", not a tool name, and name a model tier ("mid-tier"), not a model.
- Name the kind of tool a skill needs (ticket tracker, chat, code host), never the product. Have the skill list the session's tools, match each by what it can search rather than its name, and report a kind with no tool as unsearched, not empty.

## Skill conventions

- **Name.** Start with the verb for the skill's kind of job, so a developer can guess the command: `setup` or `add` builds harness pieces, `verify` proves a change works, `audit` inspects the harness itself, `explore` hunts for unknown bugs, `explain` tells someone what the harness has and how far to trust it ([ADR 0009](docs/adr/0009-explain-why-to-trust-the-harness.md)). A new kind of job gets a new verb only when none of these fits. After the verb, name the question the skill answers so two skills with the same verb read apart, with no shared prefix ([ADR 0008](docs/adr/0008-name-skills-by-verb-and-question.md)). The one exception is verification-framework, the starting skill that runs the others, which is named after the framework ([ADR 0010](docs/adr/0010-a-starting-skill-that-runs-the-others.md)).
- **Invocation.** verification-framework, setup, audit, exploration, and PR verification skills run only when called: set `disable-model-invocation: true` in the frontmatter and `allow_implicit_invocation: false` in `agents/openai.yaml`. The generated `verify-<app>` entry point, verify-change procedure, add-feature-checks, and add-tools allow agent invocation so verification can delegate missing proof. explain-harness also allows it, because it only reads and the teammate who needs it doesn't know its name. Keep the generated entry point thin; commands stay in settings and the procedure stays in verify-change.
- **Description.** Say what the skill does, give a few example requests that should trigger it, and end by pointing to the sibling skill for nearby jobs ("Use X to ...").
- **Body.** Open with what the skill owns ("You own ..."). Use numbered steps, and end each with a "Done when" line that can be checked. Close with Guardrails and a `Reply:` line that says what the final report contains, in the Messages shape from `rules.md` ([ADR 0007](docs/adr/0007-messages-end-with-one-short-ask.md)).
- **Guardrails.** Every skill's Guardrails open with the same four lines, word for word: change product code only in a scratch git worktree, removed afterward; drive and stop only app instances the run started or the user named, by process ID; ask before committing, pushing, posting, filing, or running anything with a real or shared side effect; never forge an event the real system would produce, and never loosen a check to turn a run green. `tests/test_guardrails.py` holds the exact wording and checks every skill; run it with `python3 -m unittest discover -s tests`.
- **Other skills by name.** A skill may load or point to another skill in this repo by its name, never by its file path. verification-framework is the exception: it opens sibling skills by path so the person-only ones stay person-only ([ADR 0010](docs/adr/0010-a-starting-skill-that-runs-the-others.md)).

## One shared contract

- The contract every harness follows is setup-verification's `references/rules.md`, which includes the evidence format, and the `settings.md` template. A skill that reads a harness follows the harness's copy and doesn't restate it. A skill that also works on a project harness this framework did not create carries only the rules it needs there.
- Skills find a harness by `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level. Keep that marker stable. The folder holding that skills directory is the project root: recipes run from it and settings resolve from it ([ADR 0016](docs/adr/0016-anchor-a-harness-on-its-project-root.md)).
- A harness owns `README.md`, `recordings.html`, `features/`, `status.md`, `tools.md`, `scripts/` (with the framework's copies in `scripts/framework/`), and `evidence/` (one folder per check) inside their directory. App settings configure mechanics, not artifact locations. Leave Git tracking and evidence retention to the team; do not edit Git ignore files.
- Setup ends at proven readiness with zero feature coverage allowed. add-feature-checks owns feature proof building and add-tools owns probes and actions; verify-change runs recipes and delegates missing proof within the agreed scope. An explicit existing-checks-only request prohibits building. Acceptance questions, missing permissions, and material scope expansion pause dependent work.
- Every harness gets `rules.md` copied unchanged; anything that applies to only one app goes in the `settings.md` template as a blank to fill in. Identical copies let a harness be checked for edits, upgraded by swapping the file, and read by anyone who knows the rules.
- When the contract changes, update `rules.md`, the `settings.md` template, `validate.py`, USAGE.md, and `docs/internals.md` in the same change. `validate.py` carries `rules.md`'s Rules version and hash, so on every `rules.md` change raise its `Rules version` line and `RULES_VERSION` together, then set `RULES_SHA256` to the hash its failing test prints. A different hash at the same version then always means an edited copy ([ADR 0021](docs/adr/0021-check-the-rules-copy.md)). A change to any framework script's formats or output also updates `docs/internals.md`. verify-change reads only the `rules.md` sections it names, so a renamed, added, or split section updates its list too.
- Skills and `validate.py` support only the current harness format. A contract change doesn't carry compatibility for harnesses built earlier ([ADR 0001](docs/adr/0001-one-harness-per-app.md)).
- Report each sub-feature only as Verified, Failed, or Not verified, as `rules.md` defines. A skill's own sorting labels, such as triage categories or verdicts, stay inside that skill.

## Scripts

- Framework scripts use Python 3 standard library only, so they run without installing dependencies. Generated app tools use the project's language, drivers, and connection settings; reads that judge state never go through the app's own models or logic.
- Exit codes: 0 means OK, 1 means it found a problem, 2 means it couldn't run.
- Unit tests sit beside the script as `test_<script>.py`. Run them with `python3 -m unittest discover -s skills/<name>/scripts`.

## Creating or changing a skill

- **Validate.** Run `npx skills add . --list`, and `claude plugin validate .` if the Claude Code CLI is installed.
- **Docs.** Add or update the skill's row in the README's skills index, and update USAGE.md wherever it describes the skill's behavior.
