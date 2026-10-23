# ADR 0006: One versioned tool writes every record

Status: Accepted. 2026-10-21.

## Problem

The trust contract was mostly prose that agents followed, and `validate.py` caught a broken rule only after the fact. Every harness held copies of the rules and several scripts that setup compared and copied by hand, and nothing noticed when an agent softened a rule in its copy. Every harness also built its own run recorder in the app's language, its own launch record, and its own doctor to prove which code was running: the most code an agent wrote per harness, the hardest step of setup, and the part most likely to drift. The doctor ran only when a skill remembered it, and a person running a check by hand never ran it.

## Decision

The framework's deterministic parts are one program, `vf.py`, Python 3 standard library only, copied into every harness's `scripts/framework/` so the copy there is its pinned version. The harness keeps everything a person reads without the tool.

- **`sync`** creates and updates the copies, records every file's SHA-256 in `framework.sha256`, refuses to downgrade a harness whose `rules.md` declares a newer `Rules version`, and refuses to overwrite a copy edited since, showing the diff. `validate.py` fails a `rules.md` that no longer matches its hash. The version line is for people and for `sync`; the hash is the only machine check.
- **`run`** runs the Doctor command from `settings.md` first and writes nothing unless it exits 0. The check appends one JSON event per line (`check`, `step`, `mark`, `recording`, `created`, `stopped`) to a report file `run` names, and `run` adds the times, the code before and after, the planned break, the doctor's output, the harness fingerprint, and the verdict from the exit code, refuses events that break the Evidence rules, writes the record atomically, builds its replay page, and refreshes `status.md`. Evidence a check wrote itself doesn't count. What the record proves is [ADR 0004](0004-judge-from-outside-and-compute-verdicts-from-evidence.md)'s decision, not this one's.
- **`verify <id>...`** runs each named behavior's check this way once and prints its status lines, starting the app with `--start` when the settings allow.
- **`start`, `stop`, and `doctor`** are an optional launcher for an app that runs its checkout's files directly: `start` records every repo's code state and the process, `stop` ends it, and `doctor` is ready only while that process runs code that still matches disk and a ready probe exits 0. An app that reloads on edit, runs from a cached container, or compiles first keeps a doctor of its own that adds evidence of the loaded version.
- **`replay` and `clip`** build each run's replay page and `recordings.html`, which lists every check's latest run, leaves planned breaks off, and reads "Didn't finish" for a stopped run, and cut clips or stills from a recorded run with ffmpeg.
- **`validate`, `code-state`, `break`, `status`, and `not-verified`** complete the set. `break` runs a planned break the way [ADR 0005](0005-credit-a-planned-break-only-to-what-it-broke.md) decides, and `status` and `not-verified` apply ADR 0004's verdict rule.

## Options we passed on

- **Install `vf` on the PATH, an MCP server, or a hosted service.** Each adds an install step, a process per agent host, or loses local scratch worktrees; the README promises Python 3 alone.
- **A library per app language.** Multiplies maintenance and contradicts "any language".
- **A single packed archive with no `rules.md` copy.** Can't be reviewed in a diff, and the rules copy is what reviewers and vf-explain read.
- **Keep each harness's run recorder and validate harder.** The same logic rewritten in every harness, and a refusal only after the work.
- **Read events from stdout.** The app under test prints into it, buffering breaks the timeline, and CI runners treat `::` lines as commands.
- **Make the launcher the only doctor.** It sees only files on disk; for containers and reloads it would report ready on a stale snapshot.
- **Leave the doctor to the skills.** Every skill ran it slightly differently, and a person running by hand never did.
- **Show planned breaks on the recordings page.** They answer whether a check can fail, which the map and vf-explain already answer.

## What changes

`vf.py` and the scripts behind it (`validate.py`, `code_state.py`, `break_session.py`, `launch.py`, `replay.py`, `clip.py`), `rules.md` (Harness layout, Doctor, Checks, Evidence), the settings template's Doctor line, the setup and verify modes, README, USAGE.md, internals.md, and architecture.md.
