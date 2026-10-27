# Verification notes

## Setup notes

Every command runs from the project root. The server runs the checkout's files directly, so the framework launcher starts it from `{checkout:kiosk}` and records the code it loaded; `server.js` serves `public/` from its own folder on every request, so a planned break's scratch copy serves its own page files, and the server needs a restart after an edit (Reloads: no). The agent may start and stop it; no login. Orders live in `data/orders.json` under the project root, which `.gitignore` keeps out of the repo. Checks drive the page with Playwright's bundled Chromium (`node -e "require('playwright')"` must work) and read orders from the data file, never through the server. Nothing here reaches an external or shared system.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Two kiosks placing orders at the same instant (the order number comes from the file length).
