# ADR 0016: Videos for people come from demo runs

Status: Proposed. 2026-11-06.

## Problem

A check run is fast and shaped to prove things: it fills forms at machine speed, signs in through the API, refuses permissions on purpose, and reloads to read state. `clip.py --demo` cut such a run into a video for reviewers by shortening every still stretch to a second, scaling to 1280 pixels, and captioning each step with the check's own wording. The result jumped, read like a test log, and could not show who was on which screen. A standalone recording script on the first converted app looked natural, at real speed with audience captions and a card at each switch between people, but it judged nothing, so it showed the look of a feature without showing that it works.

## Decision

- **Two outputs.** A check run's recording stays raw evidence for agents. A video for people comes only from a demo run: `vf.py run --demo --user-approved -- <command>`, which sets `VERIFY_DEMO=1` and `VERIFY_KEEP_RECORDING=1`, judges the record by the usual rules, adds `"demo": true`, and saves it under `evidence/demos/<check>/`, where no verdict reads. A demo never changes `status.md`, since pacing can hide a race.
- **A demo is its own scenario, written from a shot list the person approves.** It lives in the harness's `demos/`, outside `scripts/`, so no check's `harness_code` changes. It imports the harness's helpers without editing them, and each shot ends in a judged read of what it showed.
- **Pacing sits outside timed reads.** Pause before an action, hold only after a verdict; every read keeps its ordinary timeout. A scenario that can't, or whose behavior can't be seen, refuses demo mode.
- **Captions and screens ride on marks.** `mark` gains optional `caption` and `screen`; a demo run may keep one recording per screen. The page draws captions, badges, and switch cards itself from `references/demo-overlay.js`.
- **`demo.py` makes the video mechanically.** It cuts only at step marks, switches screens at the same moment of the run, encodes at full size at CRF 20, shrinks or splits at step marks to fit a size limit, checks the length, and writes stills for an agent to read. It needs no check to exist first: a demo can show a feature before its check does, and each shot's own read still fails a broken app. When an ordinary pass on the same code covers a behavior shown, the listing and `recordings.html` name it.
- **record-demo is a mode a person starts by name.** Verify-pr records a demo by default inside its one approval, and its check runs no longer keep passing videos. The Rules version rises to 9.

## Options we passed on

- **Keep cutting demos from check runs.** Removing waits and scaling down is what made them jarring, and check wording isn't written for an audience.
- **Pace the checks themselves.** Checks tell proof stories, not audience stories, and routing about a hundred call sites through a pacing layer would change every check's harness code and stale every pass.
- **A standalone script with no reads.** It shows the look, not that the feature works.
- **Caption fields in the feature files.** They would drift from the code that shows each step.

## What changes

`rules.md` (layout, marks, Demo runs), `vf.py run --demo`, new `demo.py` and `vf.py demo`, `clip.py` without `--demo`, `replay.py`'s Demos section, the record-demo mode, verify-pr's demo, the overlay template and Playwright example, USAGE.md, internals.md, and architecture.md.
