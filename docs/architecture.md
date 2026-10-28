# Architecture

The framework has two parts. This repo publishes the skills and one shared contract. Each app's repo gets a **verification harness**: the folder holding that app's manifest, tools, checks, results, and evidence. Skills hold the procedures, the contract defines what a pass means, and the harness holds everything specific to one app.

Use this page to decide where a change belongs. [USAGE.md](../USAGE.md) covers what a person running the skills sees, [internals.md](internals.md) the harness's files and scripts, and [design.md](design.md) open questions and decision records.

## The two parts

```mermaid
flowchart LR
  subgraph framework[This repo]
    skills[Skills<br/>procedures]
    contract[Shared contract<br/>rules.md, manifest template,<br/>framework scripts, app skill template]
  end
  subgraph app[App repo]
    entry[verify-&lt;app&gt;/SKILL.md<br/>thin entry point]
    harness[(Harness<br/>manifest, features, checks,<br/>results, evidence)]
  end
  contract -->|copied by setup| harness
  skills -->|read and write| harness
  entry -->|delegates to vf| skills
```

This repo holds one skill, `skills/vf/`, with a mode for each job ([ADR 0014](adr/0014-one-skill.md)). Setup, the two audits, and verify-pr run only when the person asks for them by name; verify, add-checks, add-tools, and explain an agent may start for its own change or question. Each mode's procedure is one file in `references/`. The shared contract lives in the same `references/` and `scripts/`, because the setup mode is what copies it into a harness. Setup also commits a copy of the skill, without `scripts/`, beside the harness, so a clone of the app's repo is the install ([ADR 0007](adr/0007-the-framework-ships-inside-the-app-repo.md)).

A harness is a `verify-<app>/` folder in one of the app's skills directories. The folder holding that skills directory is the **project root**: the repo's top folder for a single-repo app, or the app's own folder in a monorepo. Commands run from it and the manifest's paths resolve from it ([ADR 0001](adr/0001-one-harness-per-app.md)). One harness can cover an app that spans several repos.

## Layers of the contract

Each fact has one home. Put a change in the layer that owns it.

| Layer | Owns | Lives in | Who changes it |
| --- | --- | --- | --- |
| Rules | What a pass means, the evidence and feature map formats, report words, harness layout | `rules.md`, copied unchanged into every harness | This repo only |
| Message shape | How every mode asks, previews, and reports | `references/messages.md` | This repo only |
| Manifest | How this app starts, is driven, and is read, and which tools it has | Harness `harness.json`, from the template | Setup, then the skills that add tools |
| Procedure | The steps for each job | The mode files in this repo | This repo only |
| Entry point | Which app and which harness | Generated `verify-<app>/SKILL.md` | Setup |
| Harness artifacts | Feature map, results, tool guide, tools, checks, evidence | Fixed folders inside the harness | The skills, at run time |

Every harness gets an identical `rules.md`, so anyone can check it for edits, upgrade it by swapping one file, and read any harness once they know the rules. Anything that differs by app is a field in the manifest template, never a variation in the rules.

### The framework scripts

Two terms used throughout: the **doctor** is the harness's readiness check, a command that confirms the app is up and running the requested code. A **planned break** is a deliberate bug, made in a scratch copy of the code, that a new check must catch before its passes count.

Setup copies eight Python scripts unchanged into each harness's `scripts/framework/`: the ones a run, a verdict, a launch, or a replay needs, plus `trust_facts.py`. `vf.py` is the one command people and the skill call for runs and records; the scripts below sit behind it, and the explain mode runs `trust_facts.py` by path. The three audit scripts stay in the installed vf ([ADR 0012](adr/0012-vendor-only-what-bears-trust.md)).

| Script | Job |
| --- | --- |
| `vf.py` | The command-line entry point. `run` runs the doctor, then one check, and writes its evidence. `status` computes every verdict and writes `status.md`. `sync` creates and updates a harness's framework copies ([ADR 0006](adr/0006-one-versioned-tool-writes-every-record.md)) |
| `validate.py` | The machine-readable side of the contract: checks the manifest, the feature map, the setup gate, and that every Verified line is one it would write now ([ADR 0004](adr/0004-judge-from-outside-and-compute-verdicts-from-evidence.md)) |
| `code_state.py` | Reports each repo's commit, branch, and uncommitted changes, so every record means the same thing by "version" |
| `break_session.py` | Runs planned breaks in a scratch copy of the code, or in place in a worktree the run made for a pull request, and restores the product code afterward ([ADR 0005](adr/0005-credit-a-planned-break-only-to-what-it-broke.md), [ADR 0015](adr/0015-break-in-the-runs-own-copy-and-credit-only-a-clean-catch.md)) |
| `launch.py` | An optional launcher and doctor for an app that runs straight from its checkout |
| `replay.py`, `clip.py` | Turn a run's evidence and video into a replay page, the recordings page, and clips |


## Who owns what

```mermaid
flowchart LR
  subgraph person[modes a person starts by name]
    setup[setup] -->|creates, proves readiness| H[(Harness)]
    audit[audit-coverage, audit-weak-checks] -->|gaps and weak checks| H
    pr[verify-pr] --> H
  end
  subgraph agent[modes an agent may start too]
    app[verify-&lt;app&gt;] --> verify[verify]
    verify -->|missing proof, within scope| build[add-checks]
    build -->|missing probe or action| tools[add-tools]
    explain[explain]
  end
  verify -->|runs checks, records results| H
  build -->|adds proven checks| H
  tools -->|adds proven probes and actions| H
  pr -->|PR claims| build
  explain -->|how far can I trust it?| H
```

| Mode | Owns | Writes |
| --- | --- | --- |
| setup | A harness whose startup and doctor are proven on the real app. Ends with zero feature coverage | Skeleton, manifest, doctor |
| audit-coverage, audit-weak-checks, and verify-pr | Finding where an existing harness has drifted from the app, and testing a teammate's pull request | Harness fixes, findings, drafts |
| verify | Running proof for a change or named feature on the requested version | `evidence/`, and `status.md` through `vf.py` |
| add-checks | Feature checks, each agreed with the user and proven to fail on a planned break | Feature files, `scripts/`, tool entries |
| add-tools | Probes and actions, each proven on the real app | `scripts/`, tool entries |
| explain | Telling someone what the harness checks and how far to trust it | Nothing in the repo |

Three hand-offs carry most of the design ([ADR 0002](adr/0002-three-skills.md), whose three-skill split [ADR 0014](adr/0014-one-skill.md) reversed):

1. **Setup stops at readiness.** Proving the environment and building feature proof are separate jobs.
2. **The app entry point stays thin.** It names the harness and delegates. The procedure lives once, in the verify mode, so a fix reaches every app.
3. **Verification delegates missing proof.** The verify mode hands coverage it lacks to the add-checks mode, inside the agreed scope. A request for existing checks only turns missing coverage into reported gaps.

The weak-checks audit and verify-pr also work on a harness this framework didn't create, so they carry the few rules they need instead of relying on `rules.md`. Where the weak-checks rubric states a rule `rules.md` already has, it repeats the sentence word for word, and `tests/test_rubric.py` keeps the copies identical.

## A verification run

1. The user asks `verify-<app>` to verify a change. It loads vf in verify mode with its own directory as the harness.
2. The verify mode runs `vf.py validate`. Incomplete setup stops here with the saved blocker.
3. It previews the behaviors, actions, observations, and exclusions, and asks only about expected behavior it had to infer.
4. Missing proof goes to the add-checks mode: agree on a plan, build the check, have a separate reviewer compare check to plan, and prove the check fails on a planned break in a scratch worktree.
5. The doctor confirms the running app is ready and on the requested code in every repo.
6. Checks drive the app through its real entry points and read results from storage, responses, or the screen, never through app code ([ADR 0004](adr/0004-judge-from-outside-and-compute-verdicts-from-evidence.md)).
7. Each check reports its steps as events. `vf.py run` writes the evidence file from them and refreshes `status.md` ([ADR 0006](adr/0006-one-versioned-tool-writes-every-record.md)). The verify mode records any behavior it couldn't run with `vf.py not-verified`.

## Rules every skill shares

- Skills find a harness by looking for `verify-*/rules.md` in the skills directories of the current folder and each folder above it, up to the repo's top level. Keep that marker stable.
- A harness keeps all artifacts in fixed folders. The manifest can't move them ([ADR 0001](adr/0001-one-harness-per-app.md)).
- Skills and `validate.py` support only the current harness format. An older harness fails `validate.py` ([ADR 0001](adr/0001-one-harness-per-app.md)).
- Every skill passes the Rules version it was written for to `vf.py validate --written-for`, which fails on a mismatch and names the side to update, so a personal install can't run another procedure against the repo's harness unnoticed ([ADR 0007](adr/0007-the-framework-ships-inside-the-app-repo.md)).
- The framework adapts to a project by finding what it already has (start scripts, clients, requirement docs), not by adding options. Generated tools use the project's own language.
- The main agent synthesizes and decides. Subagents on a mid-tier model gather evidence: discovery during setup, the plan reviewer, per-feature readers in the audit, check readers in the explain mode.
- Product code changes only in scratch worktrees. Skills drive and stop only app instances they started or the user named. Anything with a real or shared side effect needs the user's OK, and a harness action refuses to touch anything shared without `--user-approved`.

## Where a change goes

| You want to change | Edit |
| --- | --- |
| What a pass means, the evidence format, or the report words | `rules.md`, the manifest template, `validate.py`, USAGE.md, and internals.md, together |
| The message shape | `references/messages.md` and USAGE.md |
| Something only some apps need | A field in the manifest template, not a rule |
| How one job is done | That mode's file under `references/`, then the eval smoke tier (`evals/README.md`) |
| Who does which job | The modes involved, USAGE.md, the README index, and an ADR |
| Which modes exist, or their names | `references/mode-*.md`, the mode table in `SKILL.md`, the README index, USAGE.md, and `tests/test_preamble.py` |
| A large or hard-to-reverse decision | A new ADR in `docs/adr/`, linked from design.md |

A change to a script's formats or output also updates [internals.md](internals.md). [AGENTS.md](../AGENTS.md) has the repo rules and skill conventions.
