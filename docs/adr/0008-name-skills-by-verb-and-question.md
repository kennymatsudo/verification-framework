# ADR 0008: Name skills by a verb, then the question they answer

Status: Accepted. 2026-10-16.

## Problem

Most skills run only when a person types their name, so the name has to say which one to type. Earlier names used a different verb for every skill, with overlaps (maintain-verification described itself as an audit), named the project instead of the job, or read as the wrong job (review-against-harness sat apart from the verify skills).

## Decision

Every skill name starts with the verb for its kind of job, and the rest names the question it answers. Names carry no shared prefix.

- `setup` and `add` build harness pieces: setup-verification, add-feature-checks.
- `verify` proves a change works: verify-change, each app's verify-\<app\>, verify-pr.
- `audit` inspects the harness itself: audit-coverage (what isn't checked, or is checked against stale code?) and audit-weak-checks (which checks would still pass if what they guard broke?).
- `explore` hunts for unknown bugs: explore-bugs.
- `explain` tells someone what the harness has and how far to trust it: explain-harness ([ADR 0009](0009-explain-why-to-trust-the-harness.md)).

A new kind of job gets a new verb only when none of these fits. The one exception is verification-framework, the starting skill ([ADR 0010](0010-a-starting-skill-that-runs-the-others.md)).

## Options we passed on

- **A shared prefix such as `vf-`.** Claude Code already groups plugin skills under `/verification-framework:`, and the prefix doesn't fit the generated verify-\<app\>.
- **build-verification.** Read as "build the feature".
- **add-checks.** On a code host, "checks" means a pull request's CI status.
- **add-feature-verification.** "Verification" is the verify skills' job, so the names blur.
- **setup-verification-framework.** Names the project, not the job; setup only proves readiness, and "verification" says what is set up.
- **sync-harness or refresh-harness for the coverage audit.** Names the upkeep, not the question a teammate asks.
- **check-harness-checks.** Repeats itself.
- **audit-missing-checks.** Drops the stale-check half of the job.
- **review-pr for the PR skill.** Clashes with general-purpose skills that read a PR's code for defects.
- **Keep the names and fix the descriptions.** The names alone still wouldn't say what to type.

## What changes

AGENTS.md's naming convention. audit-weak-checks still titles its fix commits `Audit harness checks:`, so repos that already ran it keep their starting point. verify-pr's and verify-change's folders match `verify-*`, but harness discovery keys on `verify-*/rules.md`, which neither has.
