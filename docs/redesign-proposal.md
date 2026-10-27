# Proposal: a second redesign with fewer parts and the same trust

Status: proposal, 2026-10-27, reviewed once by an independent agent the same day (see "Review"). Not decided. Each numbered decision below would become its own ADR if accepted.

## The point

The trust core of this framework is right and should not change: a check drives the real app and reads from outside, a planned break aimed at a behavior must fail a step that judges it, every run records the code and the check's own fingerprint, and a script computes the verdict. What has grown around that core is the cost: three skills with duplicated text, twelve scripts copied into every app, five Markdown files with grammars a 1,200-line validator parses, and two extra settings lines that exist to repoint a running app. Most of the open questions in `design.md` are friction from that scaffolding, not from the core.

Starting over, I would keep the core nearly word for word and replace the scaffolding with four things: one way to start the app on a given checkout, fewer vendored files, one structured manifest, and one skill. The order matters: the harness contract hardens the moment harnesses exist in other repos, while skills stay cheap to change because `sync` replaces them. So the contract changes come first and the skill merge last.

## What stays

- Behaviors come from requirements or the person, agreed in a preview before anything is built.
- Checks are programs in the project's language. They report events to a file; they never write evidence or verdicts.
- The planned break: scratch copy, aimed at named behaviors, credit only to a failed step that judges the behavior, patch saved beside the record.
- The record: code of every repo the check ran (commit, branch, dirty, `dirty_hash`), the doctor's result, the check's fingerprint, events, times.
- The verdict engine: the seven conditions `internals.md` lists under "A passing run is proven", `Not verified` as the default, and `not-verified` as the only thing an agent can write.
- The message shape, the blind reviewer, the four guardrails, the approval flag on actions.
- The framework shipping inside the app repo, with hashes, so a clone is the install.
- The eval suite as the test of the skills, with hidden breaks caught as the headline number.

## What the learnings say

Each line names what it rests on. The numbers were checked by the reviewer against the current tree.

- **The validator parses prose for a third of its length.** `validate.py` is 1,188 lines. By function, about 640 compute verdicts and read evidence and Git, about 300 parse the Markdown grammars (labeled lines under headings in `settings.md`, three required H2 headings in order per feature file, a three-form proof line, five required lines per `tools.md` entry, a six-line Setup record, template blanks), and about 100 check hashes, versions, and credentials. Each grammar is also written out in `rules.md`, `internals.md`, and USAGE.md. (Measured.)
- **Skills duplicate text because they cannot share it.** The four guardrail lines appear in three skills, the harness-finding sentence in five files, the gate sentence in seven, and `messages.md` twice. Two unit tests exist only to keep the copies identical. The duplication is not caused by having three skills: vf's own mode files repeat the gate its body already ran, so most copies can go without any merge. (Counted.)
- **Three skill names buy little.** ADR 0002 split skills by who may start them. The split is one frontmatter flag in one agent and a YAML line in another, and the jobs it protects (setup, audit, verify-pr) have no side effect the approval guardrail doesn't already cover: setup writes uncommitted files and starts the app locally, audit edits the harness uncommitted, verify-pr posts only on a yes. The cost is `locate.py`, a "check its skills are installed" step, a playbook table, install lines in every skill, and three copies per skills directory per agent. (Inferred from the ADR and the skill bodies; the eval suite had no case where an agent started a person-only job unasked, because the flag made it impossible to test. The experiment below adds one.)
- **Two settings lines say the same thing.** In four of the five reference harnesses that have settings, `Run scratch code` and `After an edit` are the same `stop && start --checkout` command. The fifth, relay, repoints with a doctor flag and reloads. Both lines exist so `break_session.py` can repoint a running app; `Start` already knows how to start one. (Verified in `evals/practice/*/hidden/harness`.)
- **Most of the vendored code is not trust.** Of the 5,633 lines copied into every harness, `replay.py` and `clip.py` are 1,594 (replay pages, `recordings.html`, ffmpeg clips), the three audit scripts 551 (Python-only mutation tools for the weak-checks audit), `trust_facts.py` 364 (a second computation of what `status` already computes, for vf-explain), and `locate.py` 114. The run, record, break, launch, and verdict code is about 3,000. (Measured.)
- **Most open questions are scaffolding questions.** Of the eleven in `design.md` before this one, five are about the break session's settings and repo list (batching, several breaks per session, person-only switch and `per check`, repos a run doesn't use, `env:` fallback), one is about `validate.py`'s ordering (map before setup), and one about converting an existing harness. Four are about procedure (independent judge, requirements source, second checkout, exercising pieces on a second app). (Read.)

## The redesign

The decisions are numbered in the order to do them.

### 1. Start takes the checkout; a break is stop, start, run, stop, start

`Start` may name `{checkout:<repo>}` placeholders, which `vf` fills with the real checkout on an ordinary run and the scratch worktree during a break. `Run scratch code` and `After an edit` go away; one `Reloads: yes` or `no` line replaces them, so a hot-reloading app (kiosk's page files, the converted app) is not restarted for every break, which `design.md` names as most of a break's cost there. A break becomes: make the worktree, Stop, Start with the scratch checkout, run the check with `VERIFY_PLANNED_BREAK` set, Stop, Start with the real checkout. An app only a person can start has `Start: none` and breaks are blocked, as today.

`vf run` also exports `VERIFY_CHECKOUT_<REPO>` for every repo, so a check or doctor that starts the app itself reads the checkout from its environment. That dissolves `per check` and the relay practice repo's pointer file.

Each behavior names the `repos` its check runs. A run records and requires those; a Verified line still names every repo the check ran. A teammate without the frontend checkout can run and trust the backend checks. That settles "require only the repos a run uses." Done as [ADR 0011](adr/0011-a-behavior-names-the-repos-its-check-runs.md): the list is a `Repos: a, b.` clause on the proof line, which the manifest step migrates with the rest of the line.

The session lock stays: while a break is open, `vf run` without `VERIFY_PLANNED_BREAK` refuses, so nothing passes quietly on scratch code. The skill keeps the session open across a feature's breaks, which `break_session.py` already supports and the add-checks mode does not use; that is most of the answer to "several breaks per session." Batching several breaks into one run stays open.

The Rules version rises. This is the contract change that hardens on publish and answers two of the converted app's questions, which is why it goes first.

### 2. Vendor only what bears trust

The harness stops carrying `locate.py`, `trust_facts.py` (which becomes `vf status --json`), and the three audit scripts; they stay in the installed `vf` skill. The run, record, break, launch, and verdict code stays vendored, whether as five files or one; concatenating them buys little, since `framework.sha256` already hashes a list and the "predates the framework" branch keys on a missing subcommand.

The viewer (`replay.py`, `clip.py`) is a separate decision to make explicitly. Keeping it vendored costs 1,594 standard-library lines per harness and keeps `recordings.html` and replay pages for the teammate who never installed the framework. Moving it to the install drops those for that teammate, which partly reverses ADR 0007, whose point was that teammate. The same reversal applies to the weak-checks audit, which the committed vf runs from the harness's `scripts/framework/` today. The ADR for this decision names what the non-installing teammate loses, or keeps the viewer vendored. My preference is to keep the viewer vendored and move the rest.

### 3. One manifest for everything a script reads; prose stays prose

Every field a script reads today moves into structured JSON with one schema and one parser: setup status and blocker, requirements source, repos, commands, tools (command, permissions, limits), and behaviors (id, words, source, check command, reads, repos, or the gap). The behaviors live in one JSON file per feature, beside that feature's prose, so a team's add-checks changes don't all land in one file; the reviewer flagged a single manifest as a merge-conflict surface the current layout doesn't have.

`features/<slug>.md` stays, as free prose with no grammar: how a user reaches it, the agreed plan with its sources, gotchas. `notes.md` stays as free prose. `tools.md` and `status.md` are rendered by `vf`, never authored: `tools.md` stays a file because project agent instructions link to it, and `status.md` is still the one file a script writes and nobody edits.

What this removes: the feature-map grammar, the proof-line grammar, the tools.md grammar, the Setup record grammar, template-blank detection, the "guide and help must agree" check, and roughly 300 to 400 lines of `validate.py`. The credential scan, path-exists checks, and ID uniqueness survive. `rules.md` shrinks to the trust rules (reads from outside, actions, checks, evidence, verdicts) plus a pointer to `vf schema`. It settles "check the map before setup is ready" (one pass over structured files) and most of "bring an existing harness in" (write the manifest and a reporter).

Why JSON: the standard library reads and writes it, agents edit it reliably, and reviewers diff it. TOML reads in the standard library but cannot be written by it, and `vf` must write setup status. The cost is that a person reads JSON less comfortably than `settings.md`; the rendered `status.md` is where people read.

### 4. One skill, plus the app's entry point

`vf` is the only framework skill, and it is agent-invocable. Its modes are the eight jobs: setup, add-checks, add-tools, verify, verify-pr, audit-coverage, audit-weak-checks, explain. Setup creates the thin `verify-<app>` entry point as today, which stays the everyday name and the per-app trigger.

Who may start a job becomes a rule inside the mode, not a property of a skill: setup, audit, and verify-pr open with "run only when the person asked for this by name in this session; otherwise offer it in one line and stop." Because an agent picks a skill from its description before reading its body, the merged description must not offer setup, audit, or verify-pr as triggers while still answering `/vf set up`. The eval case `verify-bare-offers-setup` is the guard: an agent asked to verify in a repo with no harness must offer setup and build nothing.

What this removes: `locate.py`, the playbook table, the install-check step, three copies per skills directory, the duplicated guardrail and gate sentences, one `messages.md`, and the two tests that keep copies aligned. It reverses ADR 0002's three-skill decision and keeps its other decisions (modes as whole files, setup stops at readiness, thin entry point, ownership between modes).

Tradeoff: an agent could start setup or an audit on its own judgment. The exposure is cost and noise rather than trust (setup spawns a discovery subagent; verify-pr can run for hours), and the eval case is the only guard. This goes last because `sync` makes skills cheap to change after publishing, and because the risk can be tested now without merging anything (see "Review").

### 5. The harness lives beside the code, not inside a skills directory

The harness moves to `verify/` under the project root (`apps/orders/verify/` in a monorepo), and each agent's skills directory gets only the thin `verify-<app>/SKILL.md` and the `vf` skill copy. Evidence and videos stop living in a folder agents scan for skills, a repo whose team uses no agent directory still has a harness, and the finder looks for `verify/harness.json` up the tree instead of `verify-*/rules.md` in four kinds of skills directory. I marked this taste; the reviewer ranks it higher for the first two reasons. Not trust-relevant either way.

## What a developer notices

- One framework name, `/vf`, and their app's `verify-<app>`. The same questions at the same points, ending on the same `Needs you:` line.
- Setup leaves `verify/` with the manifest, `rules.md`, the framework's run and verdict scripts, `scripts/`, `evidence/`, `notes.md`, and rendered `status.md` and `tools.md`, instead of twelve scripts, three skill copies, and seven Markdown files with rules about their headings.
- Adding checks edits one JSON entry per behavior and writes prose in the feature file freely. A planned break restarts the app through `Start` with the scratch checkout, or not at all when the app reloads; there are no extra settings to fill.
- `status.md` reads the same, and Verified means the same.
- Fewer stops for "the harness predates the framework" or a version mismatch.
- If the viewer moves to the install: the recordings page and clips need it installed. Failures still save a screenshot, the page text, and logs in the evidence folder.

Which trust promise it strengthens: none is weakened, and "a record anyone can rerun" gains per-check repos. The gain is in how much a skill must read and how many places a format can be mis-authored or drift.

## Cost and sequence

Cost: `vf.py`, `validate.py`, and `break_session.py` rewritten around the manifest and the Start change, `rules.md` and the settings template replaced by the schema, every mode file touched for paths and commands, five reference harnesses in `evals/practice/*/hidden` re-authored, the converted pilot re-converted, the test modules updated, and the smoke tier re-run at each step. Weeks of one person with an agent, not days. The window to pay it is now: nothing is published and one app has a harness.

If we did nothing: the open questions get answered one at a time inside the current shape, each adding a settings blank or a validator branch, and the contract hardens around the one Python pilot's shape. That is viable; the current design scores 1.0 on the smoke tier.

Sequence, each step its own ADR and its own smoke run, so a regression is caught where it was made:

0. **The invocation experiment, without merging.** On a branch, make vf agent-invocable and add the `verify-bare-offers-setup` case. Run the smoke tier. This settles the one open question about decision 4 in a day.
1. Decision 1 (Start takes the checkout, `Reloads`, `VERIFY_CHECKOUT_<REPO>`): done as ADR 0010 and ADR 0011.
2. Decision 2 (vendor only what bears trust): done as ADR 0012 for the audit scripts, with the viewer kept vendored; `locate.py` leaves with decision 4 and `trust_facts.py` with decision 3.
3. Decision 3 (the manifest, per feature): done as ADR 0013, with the behaviors' `repos` lists from ADR 0011 carried into the JSON entries. `validate.py` did not shrink as predicted, `rules.md` keeps a JSON example rather than pointing at a schema command, and `trust_facts.py` was ported rather than folded into `vf.py status`; the ADR says why.
4. Decision 4 (one skill), then 5 if wanted.

## Review

An independent agent with no view of the author's reasoning read the repo first, formed its own view, then critiqued this document (2026-10-27). It arrived at the same content with the opposite sequence and recommended proceeding with changes, all of which are folded in above:

- The sequence: contract first, skill merge last, and test the invocation risk by flipping the flag before merging anything.
- Corrections: the validator's prose parsing is about 300 lines, not the 900 the first draft implied, so the manifest removes 300 to 400 lines rather than 700; four of five reference harnesses have identical scratch-code lines, not five of six; two tests keep skill copies aligned, not three (`test_rubric.py` aligns the weak-checks rubric with `rules.md` for foreign harnesses and survives any merge).
- Costs the first draft understated: a single manifest as a merge-conflict surface; `tools.md` needing a rendered file, not only a command; the viewer and audit move as a partial reversal of ADR 0007; a `Reloads` line to keep the break saving on hot-reloading apps; the gate-sentence duplication being removable today without a merge.

The experiment in step 0 ran on branch `claude/wizardly-turing-t4wuhr` the same day: vf's `disable-model-invocation` removed, its `agents/openai.yaml` allowing implicit invocation, and `evals/cases/verify-bare-offers-setup` added. The new case ran twice (0.69 for an ask-placement miss, then 1.00) and the six smoke cases all scored 1.00; no run started setup, an audit, or PR verification unasked. The result is recorded under "Fourth run" in `evals/README.md`. One limit: in both runs of the new case the agent chose vf-verify, not vf, so the experiment clears the flag flip but not the merged description, which only the merge itself can test; the case stays as that test.

## What I did not verify

- That an agent with one model-invocable skill does not start setup or an audit unasked. The experiment is the test.
- That JSON editing by agents costs no more questions or mistakes than the Markdown grammars did. The reference harnesses and one smoke run would show it.
- That `Start` with `{checkout}` placeholders covers the converted pilot's stack, whose stack settings and process records live under the harness repo. The person-only switch case stays unsettled either way.
- That one manifest causes merge conflicts in practice. Inferred from the layout, not observed; the per-feature split costs little either way.
