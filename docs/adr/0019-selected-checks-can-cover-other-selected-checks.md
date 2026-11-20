# ADR 0019: Selected checks can cover other selected checks

Status: Accepted. 2026-11-18.

## Problem

A focused check saves time when a change affects one feature. When a change also selects a journey that exercises that feature, grouping exact commands still runs both. Inferring coverage from command names or removed flags can silently skip a different locale or answer path.

## Decision

An optional manifest `check_coverage` object declares additional behaviors a mapped command judges. The planner removes a selected command only when another selected command covers all its assigned requested IDs. It never adds a broader command. Every selected run must report steps judging its assigned requested IDs, or its evidence is refused. A refusal stops verification before historical verdicts are read. A command that judges more behaviors records every repo they require. A read-only `--plan` shows the resulting commands.

## Options we passed on

- Infer coverage from flags or names: these do not establish which assertions run.
- Reuse old passing evidence: it cannot prove the replacement judged the requested behavior in this run.
- Always run both: it loses the benefit of focused checks when a broader journey is already needed.

## What changes

`vf.py` selects commands and checks their assigned assertions; `validate.py` checks coverage declarations. The manifest template, rules, USAGE and internals describe the optional field. Rules version stays 10 because manifests without the field retain their selection and evidence format. CLI unit tests cover selection, variants, missing assertions and repository recording; the converted app supplies live integration evidence. No skill procedure or wording changes.
