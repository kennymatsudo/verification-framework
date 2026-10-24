# ADR 0008: Fingerprint what a check could load, not the whole harness

Status: Accepted. 2026-10-23.

## Problem

[ADR 0005](0005-credit-a-planned-break-only-to-what-it-broke.md) made every run record `harness_code`, a hash of every file under the harness's `scripts/`, so a check edited after its planned break loses its proof. The scope was the whole folder, and the harness lives in the app's repo, so any edit to any harness script uncalibrated every behavior at once: a teammate's merge from main that touched one check, a formatter run, a deleted dead script, or a clone that rewrote line endings. Each flip costs a rerun of every check and a replay of every break, for checks whose code never changed. Nothing in the fingerprint distinguished a check's own code from its neighbors'. `settings.md`, which decides which doctor ran and which app the check drove, was not in the fingerprint at all.

## Decision

- **Scope the fingerprint by the checks folder.** Each check's entry is one file or one folder under `scripts/checks/`. A run fingerprints the entry the command names, everything under `scripts/` outside `checks/`, `settings.md`, and any file the command names. Other entries under `checks/` are left out, since the named check cannot load them without reaching into another check's folder. A command that names no entry gets all of `checks/`, so a check run by module name or through a test runner keeps today's scope rather than none.
- **Hash with line endings normalized.** The same normalization `framework.sha256` uses, so a checkout's CRLF conversion is not an edit. Bytes are otherwise hashed as they are: a comment or formatting change still counts, since telling it apart from a loosened step would need a parser per language.
- **`settings.md` is part of the fingerprint.** A changed doctor, start, or scratch command changes what a pass means, so it waits for a rerun like a changed check.
- **`vf.py status` prints the out-of-date warnings** that `validate.py` already printed: a pass behind HEAD, a pass whose commit is no longer in HEAD's history after a rebase or branch switch, or a pass on uncommitted code. Verdicts still never depend on HEAD. A pass is about the commit it names, and the warning tells the reader this checkout is a different one.

An existing harness pays once: its older records fingerprint the whole folder, so the first edit to any sibling check after the upgrade asks for one rerun and one replay per behavior, after which the narrower scope holds.

## Options we passed on

- **Record the files the check actually loaded.** `vf.py run` starts the check as a plain subprocess in any language, so the list would be self-reported, and a shell probe run by path, a fixture opened by name, or a subprocess would be invisible. A dependency left off the list keeps a Verified it should lose.
- **Hash parsed syntax instead of bytes.** Would ignore comments and formatting, but `ast.dump` differs across Python versions, so teammates on different interpreters would disagree on an unchanged file, and it does nothing for shell or data files.
- **Keep the whole folder.** Every merge from main uncalibrates every behavior.
- **One folder per behavior.** Journeys whose steps depend on each other would pay their setup once per behavior, which ADR 0005 already rejected.

## What changes

`harness_code`, `harness_edited_since_run`, and `stale_commit_warning` in `validate.py`; `vf.py status`; `rules.md` (Tools, Evidence); vf-verify's `references/harness-code.md`; `docs/internals.md`.
