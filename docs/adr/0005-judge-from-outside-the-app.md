# ADR 0005: Drive through the app, judge from outside it

Status: Accepted. 2026-10-09.

## Problem

If harness tools reuse the project's clients, a check can read state through the app's own models and logic. Then the product grades itself: if the change under test, or an existing bug, makes the app's `Order` model report `pending` as `paid`, the check passes even though nothing about the check changed.

## Decision

Actions go through the real entry point a user or operator uses. The read that decides a verdict (a database row, the rendered screen, a raw HTTP response, a sent message) uses only the project's language, third-party drivers, and connection settings, never the app's models, serializers, or business logic. Probes, shared reads, and invariants follow the same rule, because checks judge through them.

A direct read can break when the schema changes. That is a clear failure; a read through app code risks a silent wrong pass.

## Options we passed on

- **Reuse app clients and flag checks that import code the change edited.** Catches the change, but not an existing bug in the code the check reads through.
- **Have `check.py` detect app imports.** The checker is Python-only and can't reliably read imports in other languages.

## What changes

`rules.md`, USAGE.md, and AGENTS.md limit reuse of the project's clients to connecting. The check review before a new check runs and the probe proof confirm that deciding reads use no app code. audit-weak-checks has a rubric item for it.
