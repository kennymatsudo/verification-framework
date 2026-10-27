# Proposal: a second redesign with fewer parts and the same trust

Status: proposal, 2026-10-27. Not decided. Each numbered decision below would become its own ADR if accepted.

## The point

The trust core of this framework is right and should not change: a check drives the real app and reads from outside, a planned break aimed at a behavior must fail a step that judges it, every run records the code and the check's own fingerprint, and a script computes the verdict. What has grown around that core is the cost: three skills with duplicated text, twelve scripts copied into every app, five Markdown files with grammars a 1,200-line validator parses, and two extra settings lines that exist to repoint a running app. Most of the open questions in `design.md` are friction from that scaffolding, not from the core.

Starting over, I would keep the core nearly word for word and replace the scaffolding with four things: one skill, one structured manifest, one vendored file, and one way to start the app on a given checkout.

## What stays

- Behaviors come from requirements or the person, agreed in a preview before anything is built.
- Checks are programs in the project's language. They report events to a file; they never write evidence or verdicts.
- The planned break: scratch copy, aimed at named behaviors, credit only to a failed step that judges the behavior, patch saved beside the record.
- The record: code of every repo the check ran (commit, branch, dirty, `dirty_hash`), the doctor's result, the check's fingerprint, events, times.
- The verdict engine: the seven conditions `internals.md` lists under "A passing run is proven", `Not verified` as the default, and `not-verified` as the only thing an agent can write.
- The message shape, the blind reviewer, the four guardrails, the approval flag on actions.
- The eval suite as the test of the skills, with hidden breaks caught as the headline number.

## What the learnings say

Each line names what it rests on.

- **The validator is mostly a prose parser.** `validate.py` is 1,188 lines. Its verdict engine (`compute_verdict`, `record_problems`, `check_break`, `harness_code*`) is about 300 of them. The rest reads labeled lines under headings in `settings.md`, three required H2 headings in order in each feature file, a three-form proof line, five required lines per `tools.md` entry, a six-line Setup record, and template blanks. Every one of those grammars is also written out in `rules.md`, `internals.md`, and USAGE.md. (Measured on the current tree.)
- **Skills duplicate text because they cannot share it.** The four guardrail lines appear in three skills, the harness-finding and gate sentences in seven files, `messages.md` twice, and the rubric repeats `rules.md` sentences. Three unit tests exist only to keep the copies identical. (Counted.)
- **Three skill names buy little.** ADR 0002 split skills by who may start them. The split is enforced by one frontmatter flag in one agent and a YAML line in another, and the jobs it protects (setup, audit, verify-pr) have no side effect the approval guardrail doesn't already cover. The cost is `locate.py`, a "check its skills are installed" step, a playbook table, install lines in every skill, and three copies per skills directory per agent. (Inferred from the ADR and the skill bodies; the eval suite has no case where an agent started a person-only job unasked, because the flag made it impossible to test.)
- **Two settings lines say the same thing.** In five of the six reference harnesses, `Run scratch code` and `After an edit` are the same `stop && start --checkout` command. The sixth is `reloads`. Both exist so `break_session.py` can repoint a running app; `Start` already knows how to start one. (Verified in `evals/practice/*/hidden/harness`.)
- **Most of the vendored code is not trust.** Of the 5,633 lines copied into every harness, `replay.py` and `clip.py` are 1,594 (replay pages, `recordings.html`, ffmpeg clips), the three audit scripts 551 (Python-only mutation tools for the weak-checks audit), `trust_facts.py` 364 (a second computation of what `status` already computes, for vf-explain), and `locate.py` 114. The run, record, break, launch, and verdict code is about 3,000. (Measured.)
- **Most open questions are scaffolding questions.** Of the eleven in `design.md`, five are about the break session's settings and repo list (batching, several breaks per session, person-only switch and `per check`, repos a run doesn't use, `env:` fallback), one is about `validate.py`'s ordering (map before setup), and one about converting an existing harness. Four are about procedure (independent judge, requirements source, second checkout, exercising pieces on a second app). (Read.)

## The redesign

### 1. One skill, plus the app's entry point

`vf` is the only framework skill, and it is agent-invocable. Its modes are the eight jobs: setup, add-checks, add-tools, verify, verify-pr, audit-coverage, audit-weak-checks, explain. Setup creates the thin `verify-<app>` entry point as today, which stays the everyday name and the per-app trigger.

Who may start a job becomes a rule inside the mode, not a property of a skill: setup, audit, and verify-pr open with "run only when the person asked for this by name in this session; otherwise offer it in one line and stop." The eval suite gets the case the flag made untestable: an agent asked to verify in a repo with no harness must offer setup and build nothing.

What this removes: `locate.py`, the playbook table, the install-check step, three copies per skills directory, two of three guardrail copies, six of seven gate-sentence copies, one `messages.md`, and the three tests that keep copies aligned. It reverses ADR 0002's three-skill decision and keeps its other decisions (modes as whole files, setup stops at readiness, thin entry point, ownership between modes).

Tradeoff: an agent could start setup or an audit on its own judgment. Setup creates a folder and starts the app locally, which the guardrails already allow; audit edits harness files uncommitted; verify-pr posts nothing without approval. I judge the exposure small and testable. The thing that would change my mind: a smoke run where the one-skill agent runs setup or audit unasked.

### 2. One manifest for everything a script reads; prose stays prose

Every field a script reads today moves into one file, `harness.json`, with one schema and one parser:

```json
{
  "framework": "4",
  "setup": {"status": "incomplete", "blocker": "...", "next": "..."},
  "requirements": "REQUIREMENTS.md",
  "repos": {"app": "."},
  "commands": {
    "start": "python3 verify/vf.py start --checkout app={checkout:app} --until \"curl -sf http://127.0.0.1:8071/health\" -- python3 {checkout:app}/ledger/server.py",
    "stop": "python3 verify/vf.py stop",
    "doctor": "python3 verify/vf.py doctor --probe \"curl -sf http://127.0.0.1:8071/health\"",
    "ready_line": "ready"
  },
  "tools": {
    "probe": {"command": "python3 verify/scripts/probe.py", "permissions": "read-only", "limits": "..."}
  },
  "behaviors": {
    "transfers.move": {
      "feature": "transfers",
      "words": "a transfer debits the source and credits the destination by the same amount",
      "source": "REQUIREMENTS.md LR-5",
      "check": "python3 verify/scripts/checks/transfers.py",
      "reads": "state",
      "repos": ["app"]
    },
    "transfers.daily-limit": {"feature": "transfers", "words": "...", "source": "LR-7, undecided", "check": null, "gap": "No check yet."}
  }
}
```

`features/<slug>.md` stays, as free prose with no grammar: how a user reaches it, the agreed plan with its sources, gotchas. `notes.md` stays as free prose. `tools.md` and `README.md` are no longer authored: `vf status` renders `status.md` with the results, and `vf tools` prints the guide from the manifest and each tool's `--help`. `status.md` is still the one file a script writes and nobody edits.

What this removes: the feature-map grammar, the proof-line grammar, the tools.md grammar, the Setup record grammar, template-blank detection, the "guide and help must agree" check, and about 700 lines of `validate.py`. `rules.md` shrinks to the trust rules (reads from outside, actions, checks, evidence, verdicts) plus a pointer to `vf schema`. It settles "check the map before setup is ready" (one pass over one file) and most of "bring an existing harness in" (write a manifest and a reporter).

Why JSON: the standard library reads and writes it, agents edit it reliably, and reviewers diff it. TOML reads in the standard library but cannot be written by it, and `vf` must write setup status. The cost is that a person reads `harness.json` less comfortably than `settings.md`; the rendered `status.md` is where people read.

### 3. One vendored file; viewers and audit tools stay in the install

The harness carries one framework file, `vf.py`, holding run, verify, status, not-verified, validate, code-state, break, start, stop, doctor, and sync: today's `vf.py`, `validate.py`, `code_state.py`, `break_session.py`, and `launch.py`, about 2,500 lines after the manifest removes the prose parsing. One plain Python file is diffable, which is why the packed archive was rejected before, and its hash is one line.

`replay.py` and `clip.py` ship in the installed `vf` skill as an optional viewer. Evidence folders are already self-describing (JSON, screenshots, page text, console and request logs, video), so a failure is diagnosed without them; `recordings.html` and clips appear when the viewer is installed. `trust_facts.py` becomes `vf status --json`, since status already computes every fact it gathers. The three audit scripts stay in the install; the weak-checks audit already runs them against harnesses this framework did not build.

What this removes: eleven vendored files, most of `framework.sha256`, the "predates the installed framework" branches, and the settled-on-one-Python-harness surface the design doc asks to exercise on a second app.

### 4. Start takes the checkout; a break is stop, start, run, stop, start

`Start` may name `{checkout:<repo>}` placeholders, which `vf` fills with the real checkout on an ordinary run and the scratch worktree during a break. `Run scratch code` and `After an edit` go away. A break becomes: make the worktree, Stop, Start with the scratch checkout, run the check with `VERIFY_PLANNED_BREAK` set, Stop, Start with the real checkout. An app that reloads on edit sets `Start` to its reload-safe start and the sequence is harmless. An app only a person can start has `start: null` and breaks are blocked, as today.

`vf run` also exports `VERIFY_CHECKOUT_<REPO>` for every repo, so a check or doctor that starts the app itself reads the checkout from its environment. That dissolves `per check` and the relay practice repo's pointer file.

Each behavior names the `repos` its check runs. A run records and requires those; a Verified line still names every repo the check ran. A teammate without the frontend checkout can run and trust the backend checks. That settles "require only the repos a run uses."

The session lock stays: while a break is open, `vf run` without `VERIFY_PLANNED_BREAK` refuses, so nothing passes quietly on scratch code. The skill keeps the session open across a feature's breaks, which `break_session.py` already supports and the add-checks mode does not use; that is most of the answer to "several breaks per session." Batching several breaks into one run stays open.

### 5. The harness lives beside the code, not inside a skills directory

Optional, and the most taste-adjacent item here. The harness moves to `verify/` under the project root (`apps/orders/verify/` in a monorepo), and each agent's skills directory gets only the thin `verify-<app>/SKILL.md` and the `vf` skill copy. Evidence and videos stop living in a skills folder, a repo whose team uses no agent directory still has a harness, and the finder looks for `verify/harness.json` up the tree instead of `verify-*/rules.md` in four kinds of skills directory. If this one is dropped, the other four stand.

## What a developer notices

- One framework name, `/vf`, and their app's `verify-<app>`. The same questions at the same points, ending on the same `Needs you:` line.
- Setup leaves `verify/` with `harness.json`, `rules.md`, `vf.py`, `scripts/`, `evidence/`, `notes.md`, and a rendered `status.md`, instead of twelve scripts, three skill copies, and seven Markdown files with rules about their headings.
- Adding checks edits one JSON entry per behavior and writes prose in the feature file freely. A planned break restarts the app through `Start` with the scratch checkout; there are no extra settings to fill.
- `status.md` reads the same, and Verified means the same.
- Fewer stops for "the harness predates the framework" or a version mismatch, since one file and one skill copy are checked.
- The recordings page and clips need the viewer installed. Failures still save a screenshot, the page text, and logs in the evidence folder.

Which trust promise it strengthens: none is weakened, and "a record anyone can rerun" gains per-check repos. The gain is in how much a skill must read and how many places a format can be mis-authored or drift.

## Cost and sequence

Cost: `vf.py` and `validate.py` rewritten around the manifest, `rules.md` and the settings template replaced by the schema, every mode file touched for paths and commands, seven reference harnesses in `evals/practice/*/hidden` re-authored, the converted pilot re-converted, 23 test modules updated, and the smoke tier re-run at each step. Weeks of one person with an agent, not days. The window to pay it is now: nothing is published and one app has a harness.

If we did nothing: the eleven open questions get answered one at a time inside the current shape, each adding a settings blank or a validator branch, and the contract hardens around the one Python pilot's shape. That is viable; the current design scores 1.0 on the smoke tier.

Sequence, each step its own ADR and its own smoke run, so a regression is caught where it was made:

1. One skill (decision 1). Procedure only; mechanics unchanged. Cheapest, and it tests the model-invocable risk first.
2. One vendored file, viewers optional (decision 3). Scripts only; formats unchanged.
3. The manifest, and Start with checkouts (decisions 2 and 4, together, since both rewrite settings). The big step; re-authors the reference harnesses.
4. Harness location (decision 5), if wanted.

## What I did not verify

- That an agent with one model-invocable skill does not start setup or an audit unasked. Only a smoke run can show it.
- That JSON editing by agents costs no more questions or mistakes than the Markdown grammars did. The reference harnesses and one smoke run would show it.
- That `Start` with `{checkout}` placeholders covers the converted pilot's stack, whose stack settings and process records live under the harness repo. The person-only switch case stays unsettled either way.
- The line estimates after the rewrite. The current measurements are exact; the "about 2,500" and "about 700" are estimates from reading which functions parse prose.
