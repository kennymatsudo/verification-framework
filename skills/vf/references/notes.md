# Verification notes

Copy this into the harness as `notes.md`. It holds what people and agents write beside the results: the Setup record and the caveats. `status.md` is written by `vf.py status` and never by hand. Delete an empty section only when the harness has no use for it.

```markdown
# Verification notes

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
```
