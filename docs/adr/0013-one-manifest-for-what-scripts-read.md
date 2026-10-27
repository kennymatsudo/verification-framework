# ADR 0013: One manifest for everything a script reads; prose stays prose

Status: Accepted. 2026-10-27. Third step of [the redesign](../redesign-proposal.md).

## Problem

Five Markdown files carried fields that scripts parsed by their own grammar: `settings.md` (labeled lines under headings), `notes.md` (a Setup record with six labeled lines), `features/README.md` (an index), `features/<feature>.md` (fixed headings, `- id: text` lines, and a proof line whose command, reads, repos, and break-tested reason were read by regex), and `tools.md` (entries with `Use when:`, `Run from`, and labeled lines). Each grammar was a page of `rules.md`, a parser in `validate.py`, a duplicate parser in `trust_facts.py` and the eval runner, and a class of errors an agent could make with a stray colon. A reviewer could not tell a prose edit from a contract edit, and template-blank detection had to read prose to find unfilled fields.

## Decision

Everything a script reads about an app lives in two kinds of JSON file, read by one parser in `validate.py`:

- `harness.json`, the manifest: `app`; `setup` (`status`, `target`, `findings`, `looked_in`, `blocker`, `next`, `doctor_proof`); `requirements`; `repos`; `commands` (`start`, `stop`, `doctor`, `ready_line`, `probe`, `reloads`); and `tools`, one entry per harness command (`command`, `use_when`, `permissions`, `limits`, and optional `run_from`, `inputs`, `environment`, `result`, `failure`).
- `features/<slug>.json`, one per feature: `name`, `summary`, optional `reach`, `sources`, `gotchas`, and `behaviors`, keyed by ID, each with `words` and either a `check` with `reads` (and optional `repos`, `not_break_tested`, `plan`), an `unreachable` block, or neither.

`notes.md` is free prose. `status.md` and `tools.md` are rendered by `vf.py status` and `vf.py tools`; `validate.py` fails a `tools.md` that differs from what it would render. `settings.md`, `features/README.md`, and the Markdown feature files are gone; a `features/<slug>.md` beside a JSON file is prose scripts ignore. The Rules version rises to 6.

- **Per feature, not one file.** Behaviors sit in the feature's own file so two add-checks changes don't collide in one manifest.
- **JSON, not TOML or YAML.** The standard library reads and writes it, and `vf.py` must write setup status and tool entries.
- **The rendered guide stays a file.** Project agent instructions link to `tools.md`, so it must exist; rendering it keeps one source.
- **What the proposal expected and this step did not deliver.** `validate.py` did not shrink: the grammar parsers left, and field-by-field checks, the tools renderer, and the hand-edit guard took their place, so it is about the same length. `rules.md` lost its grammars (259 to 222 lines) but keeps its layout and feature-map sections with a JSON example rather than pointing at a schema command. `trust_facts.py` was ported to the JSON files rather than folded into `vf.py status --json`; that fold waits for the one-skill step, which decides what vf-explain still needs.

## Options we passed on

- **Keep the Markdown and tighten the grammars.** Every grammar fix is a `rules.md` page, a parser, and an eval case; the errors come from the format, not its wording.
- **One manifest holding the behaviors too.** A single merge-conflict surface for every add-checks change.
- **A schema command (`vf schema`) instead of the example in `rules.md`.** One more subcommand for a format `rules.md` shows in twenty lines.
- **Let `tools.md` be hand-written and checked against the entries.** Two sources that must agree, which is the check this step removes.

## What changes

`validate.py` (new parsing layer, `render_tools`, `write_tools`), `vf.py` (`tools` subcommand, `harness_of` checks `harness.json`), `code_state.py`, `break_session.py`, `launch.py`, `replay.py`, `trust_facts.py`; `rules.md` (version 6), `references/harness.md` replacing `references/settings.md`, `references/notes.md`, `references/tool-guide.md`; every mode file that named `settings.md` or a proof line; the reference harnesses under `evals/practice/*/hidden`; the eval runner's scaffold and graders; `docs/internals.md`, `docs/architecture.md`, `docs/state-transitions.md`, USAGE.md, and AGENTS.md. A harness on the old files does not carry over: after `sync` updates its framework copies, `vf.py validate` fails until the manifest and feature files are written, by hand or by rerunning setup ([ADR 0001](0001-one-harness-per-app.md) carries no compatibility for earlier formats).
