# Verification status

Copy this into the harness as `status.md` and link it from `features/README.md`. Keep current results out of feature definitions. Delete an empty section only when the harness has no use for it.

```markdown
# Verification status

## Setup: <harness directory name>

- Target: <app or system and its boundary>
- Findings: <sourced setup facts>
- Looked in: <sources inspected>
- Blocker: <remaining setup blocker, or none>
- Next action: <answer or action needed to resume, or none>
- Doctor proof: <not run and why, or output/evidence location, date, and tested code>

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

None yet.

## Latest results

No runs yet.
```

Record each sub-feature result in Latest results as the one-line form in rules.md's Reporting section, beside the run's date and what was not proved.

For each run, record the date, check or scenario, the exact version each component ran, what passed or failed in user terms, what was not proved, and the evidence path. For Git checkouts, include commit, branch, and dirty state. Record an environment stop separately from a failed product check. Keep a result attributed to the version tested; remove a known failure only after the affected check passes on the version where it was tracked.
