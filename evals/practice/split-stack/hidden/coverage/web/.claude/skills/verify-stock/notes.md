# Verification notes

## Setup: verify-stock

- Target: the stock command-line client in this repo and the Stock API from the api repo beside it, run locally on port 8075.
- Findings: README.md:5 names `stack.env` and its two keys; stock/cli.py:11 reads them; ../api/README.md:7 gives the build and run commands and the `-X main.version` stamp; ../api/main.go:13 reads `version`; REQUIREMENTS.md holds ST-1 to ST-3; an agent with both checkouts and Go can start everything.
- Looked in: README.md, REQUIREMENTS.md, stack.env.example, stock/, ../api/README.md, ../api/main.go, ../api/go.mod.
- Blocker: none
- Next action: none
- Doctor proof: saved output in evidence/doctor/setup.txt: ready after Start (exit 0, `/version` equal to the api checkout's stamp), not ready after Stop (exit 1), on the commits recorded there.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Breaks in the web client itself: the checks run this checkout's `python3 -m stock`, so only api breaks run from a scratch copy.
