# ADR 0012: Record runs that drive a screen, and replay them from the evidence

Status: Proposed. 2026-10-13. Accept once a harness in another language records a run that replays and cuts cleanly, captions included. Its recordings index is replaced by [ADR 0020](0020-a-runs-page-that-leads-with-each-checks-latest-run.md).

## Problem

An evidence file says which step failed and what it read, but not what the user would have seen. A developer debugging a failure, or a reviewer judging a feature, wants to watch it. An agent diagnosing the failure can't watch video at all; it reads text and still images. One harness built a video, a replay page, and PR clips for itself; every other harness would rebuild them, each slightly differently, and none served the agent.

## Decision

Evidence gains a timeline. Each step records `at`, its seconds into the run; `marks` record where each step begins and each action a viewer would watch for; `recording` names a kept video and when it started. A failed step in a check that drives a screen names a `snapshot`: a screenshot and the page's text at its verdict. The run's folder, named like the evidence file, holds the video, snapshots, and console and request logs with times. A check that drives a screen keeps its video when it fails or when its environment sets `VERIFY_KEEP_RECORDING=1`, one switch that works the same in every harness.

The framework ships `replay.py` and `clip.py`, copied unchanged into each harness like `validate.py`. They read only the evidence and the video, never the app, so they work for any language.

For people: a replay page that opens on each failure, an index at `recordings.html`, created at setup, linked from the feature map, and rewritten by every run that keeps a video, listing each kept recording by check with its result, branch, and commit, and a clip with a caption bar for a PR, named for its check, steps, and start time so it reads clearly once attached.

For agents: stills from just before, at, and just after each failure, read after the snapshot text and nearby log entries. A recording shows what happened; the steps still decide the verdict.

Clip captions are drawn by a headless Chrome, Chromium, or Edge and laid over the video by stock ffmpeg, falling back to ffmpeg's subtitles filter. Any run with a video already has a screen driver, and nearly every developer machine has one of those browsers, while some common ffmpeg builds, Homebrew's default among them, can't draw text.

## Options we passed on

- **Let each harness build its own.** Every harness relearns the same work, and reviewers see a different replay per app.
- **Keep video on every run.** Large files on every pass, and retention belongs to the team.
- **Let each harness choose how to ask for a video.** A teammate would learn a different switch per app.
- **Rename run folders to readable names.** The evidence file name is part of the contract `validate.py` reads; the index and clip names give people readable names without changing it.
- **Require an ffmpeg that draws text.** The default macOS install can't, so the first run fails for most Mac users.
- **Draw captions into the page while recording.** Changes the page under test.
- **An embedded subtitle track.** GitHub's and chat tools' inline players are not known to show it (unchecked).
- **Have agents watch the video.** Most can't, and a few stills plus the page's text cost far less.

## What changes

`rules.md`'s evidence format, how agents and people read a run, and Failed reporting; `validate.py` (step times and recording paths in cited evidence); the two new scripts with tests; and USAGE.md, together. Setup copies the scripts. The code layout ([ADR 0011](0011-put-each-format-where-its-readers-look.md)) gains a screen wrapper that records, snapshots failures, and times its logs. add-feature-checks records checks that drive a screen and confirms a planned-break run snapshots the failing step. verify-change diagnoses from snapshot text, nearby logs, and stills, links the replay on a failure, and offers a clip after a recorded pass.
