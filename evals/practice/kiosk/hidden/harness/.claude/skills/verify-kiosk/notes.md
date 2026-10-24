# Verification notes

## Setup: verify-kiosk

- Target: the kiosk web page and its Node server in this repo, started locally with `node server.js` on port 8072; no external services.
- Findings: README.md:7 gives the start command and port; server.js:5 reads `KIOSK_PORT` and `KIOSK_DATA`; server.js:93 serves `public/` from the server's own folder; REQUIREMENTS.md holds the agreed behavior KR-1 to KR-6; an agent can start the app with only this checkout and Node.
- Looked in: README.md, REQUIREMENTS.md, package.json, server.js, public/app.js, tests/; no compose file or Makefile.
- Blocker: none
- Next action: none
- Doctor proof: saved output in evidence/doctor/setup.txt: ready after Start (exit 0), not ready after Stop (exit 1), on the commit recorded there.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Two kiosks placing orders at the same instant (the order number comes from the file length).
