# ADR 0003: Each skill owns one part of verification

Status: Accepted. 2026-10-09.

## Problem

Verification has three jobs: prove the environment is ready, build checks for a feature, and run checks on a change. When one skill did two of them, its name misled. When they were split strictly, a request to verify a change stopped at missing checks until the user invoked another skill. And each generated app skill carried its own copy of the procedure, so every fix had to be repeated in every app.

## Decision

- **setup-verification** proves readiness and stops ([ADR 0002](0002-setup-proves-readiness-and-resumes.md)).
- **add-feature-checks** owns acceptance agreement, feature tools and checks, independent check review, and planned-break proof. It stays directly callable.
- **verify-change** owns a whole verification request. It previews scope, delegates missing proof to add-feature-checks within the agreed scope, runs the recipes on the requested version, and records results. An explicit existing-checks-only request prohibits building. Unresolved acceptance, missing action permissions, or a material scope expansion pause dependent work; missing dependencies and blocked proof stay visible gaps.
- **verify-\<app\>**, the generated entry point, stays thin. It names its own directory as the harness and delegates to verify-change by name. `rules.md` owns the proof contract, and settings own the app's commands and startup restrictions. The app skill, verify-change, and add-feature-checks allow agent invocation so this delegation works. Setup stops before creating a harness if verify-change isn't installed.
- **Building the product is separate.** A check for wanted but unshipped behavior stays failing with a tracking issue. Building a check doesn't authorize implementing the feature, and a pass in a scratch copy never proves the user's checkout.

## Options we passed on

- **Setup also builds checks.** The entry point doesn't say it does that.
- **verify-change builds missing checks without a preview.** A run would silently change its scope and tools.
- **Require two user invocations.** Clean responsibilities, but neither finishes the request alone.
- **Fold building into verify-change.** Duplicates the builder's reusable procedure.
- **The full procedure in each generated app skill.** Fixes and commands end up with many copies.
- **No app skill.** Loses the app-specific entry point that agents discover.
- **Make verify-change run only when called.** Blocks delegation from the app skill.
- **Add an implementation loop now.** Building the feature needs its own authorized workflow.

## What changes

Each skill's `SKILL.md`, the app skill template, AGENTS.md's invocation rules, and USAGE.md.
