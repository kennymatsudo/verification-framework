# Relay feature map

Open the file for the feature you changed. Follow `../rules.md` for every proof.
Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
See each check's latest run in [the recordings page](../recordings.html).

## Baseline

- Start: `none`: relay is a command each check runs itself. Ready when `python3 .claude/skills/verify-relay/scripts/doctor.py` exits 0. Stop: `none`.
- Data: each check writes its own input and output files in its run folder.
- Isolation: none needed; runs share nothing.

## Features

None yet.
