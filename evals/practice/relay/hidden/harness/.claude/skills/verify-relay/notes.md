# Verification notes

## Setup: verify-relay

- Target: the relay command-line converter in this repo, run as `python3 -m relay`; no server, no services.
- Findings: README.md:7 gives the command; relay/cli.py:44 defines the exit codes (0 converted, 2 malformed, no output written); REQUIREMENTS.md holds CR-1 to CR-5; nothing needs a person.
- Looked in: README.md, REQUIREMENTS.md, relay/, examples/; no Makefile or package manifest.
- Blocker: none
- Next action: none
- Doctor proof: saved output in evidence/doctor/setup.txt: the doctor reports the checkout ready (exit 0), and not ready when pointed at a folder without relay (exit 1).

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Inputs with thousands of rows.
