# ADR 0017: Credit a planned break only to what it broke

Status: Accepted. 2026-10-18. Narrows the break rule in [ADR 0006](0006-back-every-verified-with-its-evidence.md).

## Problem

A planned break that failed any step counted as proof for every behavior its check covered, because evidence listed behaviors once per run and never said which step judged which. In a checkout check covering payment and the receipt, a break that skips payment also fails the receipt step, since no paid order exists to send a receipt for. Both behaviors counted as break-tested, though nobody broke the receipt, so nothing had shown the receipt step can catch a broken receipt. The framework encourages exactly these multi-behavior journeys, and the first converted app has one covering 38 behaviors.

## Decision

- **Steps name what they judge.** Each step in evidence lists its behaviors in `sub_features`. In a check that covers one behavior, a step that names none judges it, so most checks need no change. In a check that covers several, a step that names none judges none, which suits setup steps.
- **A break names its target before it runs.** The break run is started with `VERIFY_PLANNED_BREAK=<IDs>: <what was broken>`, and its evidence records `planned_break` with what was broken and the behaviors aimed at. Recording it before the outcome is known stops the credit from being chosen after the fact.
- **Credit needs both.** A break proves a behavior only when it was aimed at it and a step judging it failed. Only those steps must stay in later passing runs, still judging that behavior. A step that failed as a knock-on effect earns nothing and need not stay.
- `validate.py` and explain-harness's trust tally apply the same rule. A passing run must have a step judging the behavior it claims, and can't be a planned break run.

## Options we passed on

- **Credit any behavior whose own step failed.** The receipt step failed too, so this still gives the false credit.
- **Name behaviors in step names, such as an ID in parentheses.** No format change, but nothing checks the label and a rename silently breaks it.
- **Split every multi-behavior check into one check per behavior.** Removes the ambiguity, but journeys whose steps depend on each other pay the setup cost once per behavior.
- **Batch several breaks into one run.** Cuts the cost of breaks on apps with expensive runs; it stays open in [design.md](../design.md), and this rule keeps it from granting false credit if it lands.

## What changes

`rules.md` (Checks and Evidence), `validate.py` and its tests, explain-harness's `trust_facts.py` and its guidance, add-feature-checks' check proof steps and run recorder, USAGE.md, and `docs/internals.md`. Each harness's run recorder writes step `sub_features` and `planned_break`, and recopies `scripts/framework/validate.py`. A Verified result whose break has no `planned_break`, or whose multi-behavior check has unlabeled steps, fails until its break is rerun.
