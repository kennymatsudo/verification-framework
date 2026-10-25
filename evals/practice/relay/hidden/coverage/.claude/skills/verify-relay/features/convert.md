# Convert

A finance teammate converts an expense CSV to the upload tool's JSON.

## Sub-features

- convert.rows: every input row becomes one output row with the same name and the amount in exact whole cents.
- convert.total: the output's total equals the sum of every row's cents.
- convert.reject-malformed: a malformed amount means exit code 2, a message naming the line, and no output file written.
- convert.repeatable: converting the same input again produces an identical output file, replacing any earlier one.

## How a user reaches it

- `python3 -m relay convert INPUT.csv OUTPUT.json` from a checkout.

## Verification plan

Source: REQUIREMENTS.md CR-1 to CR-4. CR-5's other currencies are undecided and have no check.

- convert.rows: convert a four-row file whose amounts include ones a float conversion gets wrong by a cent; compare each output row with the cents CR-1 fixes for those amounts.
- convert.total: compare the output total with the sum of those expected cents.
- convert.reject-malformed: convert a file with a bad amount on line 3; expect exit 2, "line 3" in the message, and no output file.
- convert.repeatable: convert the same file twice over a stale output file; expect identical bytes and no trace of the stale content.

## How to prove it

- convert.rows: `python3 .claude/skills/verify-relay/scripts/checks/convert.py`. Reads the output file (state).
- convert.total: `python3 .claude/skills/verify-relay/scripts/checks/convert.py`. Reads the output file (state).
- convert.reject-malformed: `python3 .claude/skills/verify-relay/scripts/checks/reject.py`. Reads the exit code, the message, and the output path (state).
- convert.repeatable: `python3 .claude/skills/verify-relay/scripts/checks/repeat.py`. Reads both output files (state).
