# Verification status

Copy this into the harness as `status.md` and link it from `features/README.md`. Keep current results out of feature definitions. Delete an empty section only when the harness has no use for it.

```markdown
# Verification status

## Setup: <harness directory name>

- Target: <app or system, its known boundary, and the requested setup>
- Findings: <established facts with file:line or user-answer sources>
- Looked in: <sources inspected, including places that did not answer the question>
- Blocker: <what prevents finishing setup, or none>
- Next action: <the answer or action needed to resume, or none>
- Doctor proof: <not run and why, or the saved output in evidence/doctor/<time>.txt, date, and code versions tested>

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

None yet.

## Latest results

No runs yet. Replace each behavior's result when it changes; the last line for an ID is authoritative even without evidence.
```
