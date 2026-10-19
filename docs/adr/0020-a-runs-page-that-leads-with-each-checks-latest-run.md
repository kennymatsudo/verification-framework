# ADR 0020: A runs page that leads with each check's latest run

Status: Accepted. 2026-10-19. Replaces the recordings index in [ADR 0012](0012-record-runs-and-replay-them-from-evidence.md); the rest of 0012 stands.

## Problem

`recordings.html` listed only runs that kept a video, as a table of every run's details. A reader new to it couldn't tell what was broken. A run without a video never appeared, so in the first converted app, 4 of 7 checks never appeared, one of them failing, and the page showed "Passed 0" though 4 checks' latest runs had passed. A planned break, which fails on purpose, sat at the top as the worst failure, while that check's latest real run had passed. Every row repeated "local edits" and "not on main", which is normal on a developer's branch. And "step" meant two things: the video's chapter markers and the check's pass/fail steps.

## Decision

- **Every run is listed, so every run rewrites the page.** After writing its evidence, every check run runs `replay.py` on it, not only one that kept a video. Every run gets a replay page, and a run with no video shows its timeline and failures alone.
- **The page leads with what a developer needs first.** Under the app's name, one line per check, titled with its feature and a sentence on what that feature does: its result, its first failed step or stop reason, how many steps failed, when it ran, and a tag when its code differs from the newest run's. Details opens every failure, the behaviors judged, each repo's code, and earlier runs; the replay page holds the video and full timeline.
- **Planned breaks are left off.** Their evidence stays, since proof lines cite it; a footnote counts them and points to the feature map.
- **A stopped run reads "Didn't finish", with no verdict,** and says whether any step had failed before it stopped. "Step" on the page means only the check's pass/fail steps.

## Options we passed on

- **A second page for runs without video.** Two places to look, and the one people open would still mislead.
- **Link each `status.md` result to its run instead.** Leaves the page people open showing a fraction of the runs.
- **Show planned breaks with their own label.** They answer whether a check can fail, which the feature map and explain-harness already answer; here they only add noise.
- **Keep one row per run.** A reviewer cares about the latest run; earlier runs fit in Details.

## What changes

`replay.py` and its tests; `rules.md`'s layout and Evidence lines; add-feature-checks' run object, which runs `replay.py` after every run; setup-verification's step that creates the page; the harness README template; explain-harness's pointer to the page; USAGE.md; and `docs/internals.md`. An existing harness needs the new `replay.py` copy and that one change to its run object.
