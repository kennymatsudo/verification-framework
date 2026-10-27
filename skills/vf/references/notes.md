# Verification notes

Copy this into the harness as `notes.md`. It is free prose for what people and agents write beside the results; no script parses it beyond reading its headings. The setup status and the facts setup resumes from live in `harness.json`'s `setup` block, `status.md` is written by `vf.py status`, and `tools.md` by `vf.py tools`. Delete an empty section only when the harness has no use for it.

```markdown
# Verification notes

## Setup notes

<how the app is started and stopped, where its data lives, which commands run from where, what needs a person (a login, a prompt, an approval), and anything a run must not touch>

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

None yet.
```

A line under "Where a pass can mislead" that starts with a behavior's ID and a colon (`checkout.pay: ...`) is attached to that behavior by vf-explain.
