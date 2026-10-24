# Verification rules

Rules version: 3

Copy this file into the harness as `rules.md`, unchanged; app specifics live in `settings.md`. `scripts/framework/vf.py validate` fails a copy that differs from the one vf last synced, whose hash this harness's `framework.sha256` records with every other framework file's. A section applies once the harness has that kind of piece. A piece that cannot follow a rule names the exception in its own help text and in the feature file that uses it.

## Harness layout

Keep framework artifacts at fixed paths relative to this harness; settings cannot move them:

- `README.md`: where a person starts.
- `recordings.html`: each check's latest run and history, for people.
- `settings.md`: app configuration.
- `features/README.md`: feature index.
- `status.md`: the latest result for every behavior, written by `vf.py status` and never by hand.
- `notes.md`: what people write beside the results: the Setup record, known failing checks, where a pass can mislead, untested cases.
- `tools.md`: command guide.
- `scripts/`: the app's harness tools, with the framework scripts, copied unchanged, in its `framework/` folder.
- `evidence/<check>/`: each check's runs.
- `evidence/doctor/`: saved doctor output.
- `evidence/launch/`: the launch record and output of an instance `vf.py start` started.
- `evidence/not-verified.jsonl`: the Not verified records `vf.py not-verified` writes.
- `evidence/breaks.jsonl`: one line per planned break that caught a sub-feature, written by `vf.py break run`.

Beside the harness, the same skills directory holds `vf/`, `vf-verify/`, and `vf-explain/`: copies of the framework skills without their `scripts/`, written by `vf.py sync` and recorded in `framework.sha256` with every other framework copy, so a clone of the repo needs no install. Each other skills directory at the project root holds the same copies. Their scripts run from the framework scripts in this harness.

The project root is the folder holding the skills directory this harness sits in: `app/` for `app/.agents/skills/verify-app/`. In a single-repo app it is the repository's top folder; in a monorepo it is the app's own folder. Recipe commands run from it, and `settings.md` paths resolve from it.

Times in file names are UTC with dashes, such as `2026-10-03T14-02-11Z`, so they sort in order and read plainly. Requirements stay in their sources, linked from feature plans. Reuse the project's language, clients, and commands, but not its artifact layout.

Evidence retention and Git tracking are the team's choice; skills never edit Git ignore files or delete evidence.

## Feature map

The harness's `features/` directory has one `README.md` index and one file per user-facing feature, in the format below. `scripts/framework/vf.py validate` enforces it.

### Index: `features/README.md`

  ```markdown
  # <App> feature map

  Open the file for the feature you changed. Follow `../rules.md` for every proof.
  Read [the latest results](../status.md) and [the notes](../notes.md) for known failures, misleading passes, and untested cases.
  See each check's latest run, and watch recorded ones, in [the recordings page](../recordings.html).

  ## Baseline

  - Start: `<start command>`. Ready when `<doctor command>` exits 0. Stop: `<stop command>`.
  - Data: <seed data, test accounts, and where they come from>.
  - Isolation: <how two runs avoid sharing state, or "one instance per machine; never drive one you did not start">.

  ## Features

  - [Checkout](checkout.md): pay, saved cards, failed payment retry.
  ```

Group the list under H3 area headings once it passes about ten entries. A journey that crosses several features gets its own file that links to the per-feature files rather than repeating them.

### Feature file: `features/<slug>.md`

  ```markdown
  # Checkout

  A signed-in shopper pays for the items in their cart and sees a confirmation.

  ## Sub-features

  - checkout.pay: paying with a new card creates a paid order.
  - checkout.saved-card: a returning shopper can pay with a saved card.
  - checkout.retry: a declined card shows an error and lets the shopper retry.

  ## How a user reaches it

  - Cart page, "Checkout" button.
  - `POST /api/checkout` from the mobile app.

  ## Verification plan

  Source: <requirement or user answer establishing the intended behavior>.

  - checkout.pay: submit checkout through the real API; read the matching order and payment records to establish payment completion. This proves stored payment state, not the visible confirmation screen.
  - checkout.saved-card: No agreed proof yet.
  - checkout.retry: No agreed proof yet.

  ## How to prove it

  - checkout.pay: `bin/verify check checkout-pay`. Reads the order row and payment record (state).
  - checkout.saved-card: No check yet.
  - checkout.retry: Unreachable: the sandbox processor has no declining test card. Tried the "4000 0000 0000 0002" card.

  ## Gotchas

  - The payment webhook arrives up to 30 seconds after the redirect. Wait on the probe, not a sleep.
  ```

Rules the script enforces:

- Sub-feature lines are `- <id>: <behavior>`. IDs are lowercase, dotted or dashed, and unique across the map.
- Every sub-feature has exactly one line under "How to prove it", in one of three forms: a command in backticks, `No check yet.`, or `Unreachable: <blocker>. Tried <route>.`
- A command line may go on in plain words about what the check reads, and may end with `Not break-tested: <reason>.` when no planned break has failed it yet. Nothing writes `Break-tested` in the map: `vf.py status` computes it from the evidence, and the script fails a line that says it.
- Every path or command named in backticks under "How to prove it" exists, as a path from the project root.

Keep the feature file about intended behavior and stable ways to prove it. A current failure, a version-specific pass, or a temporary harness limitation belongs in `status.md`.

Verification plan (the agreed proof and its sources, which vf-verify settles before building), Gotchas, and a `## Request flow` section before "How to prove it" (when the code path is not obvious) are optional; leave them out when empty.

## Tool discovery

Tools are ordinary repo-local commands usable outside verification. Put new harness tools in this harness's `scripts/`, with each check's entry file or folder in its `checks/` folder; reuse existing project commands in recipes when they suffice. Use the project's language, third-party drivers, and connection settings. Python 3 is a fallback for standalone coordination when available. Keep command parsing separate from reusable reads and actions. No MCP server or universal CLI is required.

Document each harness command in `tools.md`: when to use it, what it answers, working directory and inputs, environment prerequisites, permissions and side effects, output and failure meanings, and limits. `--help` works without connecting to services or acting. Redact secrets in help examples and output, and read credentials from the project's connection settings, never from a literal in a tool or the guide. `validate.py` checks each entry's Permissions and Limits lines, Run from folder, and Help command, and flags a credential written into `tools.md` or `scripts/`; `--run-help` also runs each Help command. The other guide lines are for the reader and go unchecked. A probe's help and guide describe observations, never promise a verified feature.

The guide and `--help` must agree. Project instructions may point at the guide; the skills that build tools own that pointer and ask before editing an instruction file.

## Setup

`settings.md` has a Setup Status of `incomplete` or `ready`; incomplete settings may omit unknown required fields. `notes.md` has a `## Setup: <harness directory name>` section recording the target, sourced findings, places inspected, blocker, next action, and doctor proof. Run `scripts/framework/vf.py validate` before live verification: a `rules.md` that differs from the copy vf last synced exits 1 before anything else is checked; incomplete setup exits 2 with its resume action; invalid setup records exit 1. Finish setup with vf before driving the app or claiming coverage.

Ready means setup was proven against the real app, not that the current instance is up; run the doctor every time. Structural validation alone never proves setup.

## Code under test

Every result records the version that produced it. List every repo in `settings.md`, even when there is one. The doctor finds each checkout from its locator and reports the commit the running process actually loaded, not the checkout's current HEAD; a health response that recomputes Git metadata on request is not evidence of loaded code. A missing repo or unreadable running version stops the run.

For each Git repo, record the commit, branch, dirty state, and whether the commit is on its default branch. Dirty means a modified, staged, or untracked file outside the harness directory and the framework skill copies beside it (those `framework.sha256` records), and inside the repo's located folder when the locator names a folder within a checkout, such as a monorepo app's own folder; ignored files don't count. Record `dirty_hash` from `code_state.py`: SHA-256 of staged and unstaged diffs and untracked file names, modes, and contents, or null when clean. Capture it with the loaded version at startup; a different hash means different uncommitted code even on the same commit.

Take these from `scripts/framework/vf.py code-state`, never from Git directly, so every tool means the same by each field; `--checkout` points it at another checkout, and `on_main` is null when the repo has no default branch to compare with. A pass is evidence only for the recorded versions.

## Doctor

The doctor command in `settings.md` is read-only. It answers one question: is this instance worth driving?

- It reports whether each process is up, which code each one runs, which ports it holds, and whether auth is valid.
- Exit 0 means ready. Exit 1 means not ready, with each reason on its own line. Exit 2 means it could not tell.
- It prints the exact ready line in `settings.md`, which tools may match on. Change the line only together with every tool that matches it.

`scripts/framework/vf.py run` runs it from the project root before every check and stops, running nothing, unless it exits 0; the evidence records its exit code and the end of its output as `doctor`. A harness whose `Run scratch code` is `per check` starts the app inside each check, so `vf.py run` skips the doctor there and records `"doctor": "per check"`.

Start and Stop in `settings.md` pair with it. Stop stops only what Start recorded and removes that launch record; stop an instance the harness started with Stop, never by killing its processes. Start replaces a launch record whose processes have exited, so a crash or reboot never blocks the next start.

`scripts/framework/vf.py start`, `stop`, and `doctor` are a launcher a harness may use for these three lines when the app runs the checkout's files directly. `start` records every repo's code state and the process it starts, `stop` ends that process and removes the record, and `doctor` is ready only when the process is up, the code on disk still matches the record, and the ready probe it is given exits 0. It knows only what was on disk at start: an app that reloads on edit, runs from a container built from a cache, or compiles before starting needs a doctor that adds its own evidence of the loaded version.

## Probes

A probe answers a question about current state: the probe command in `settings.md`, then `<question> <args>`.

- **Read-only.** Database reads run in a read-only transaction. HTTP calls are GET only.
- **One JSON object on stdout.** Concise by default, with `--full` for the raw object.
- **Exit codes.** 0 answered. 1 not found, with `{"not_found": ..., "hint": ...}`. 2 could not answer, with `STOPPED: <reason>` on stderr. A reader can always tell "none found" apart from "could not read".
- **Hints.** `next` lists follow-up probe commands.
- **Secrets.** Redact any value whose key looks like a secret, token, or password.
- **Shared reads.** A check that needs the same fact calls the same read function the probe uses, so a probe can re-check any verdict. A read returns nothing only on not-found and raises on any other failure, so a check can't mistake an outage for an empty result.
- **Read from outside the app.** Read the stored row, the raw response, or the rendered screen directly. The read that decides a verdict, and any read it calls, imports none of the app's models, serializers, or business logic; a read through app code passes whenever that code is wrong in the same way the behavior is. A response from the app's own API is still built by its code: a probe that reads one says so in its Limits, and a check judging behavior that endpoint implements reads storage or the outside system instead.

## Actions

An action does something a real user or operator would do, through the same entry point they use.

- **Approval flag.** An action with a real or shared side effect refuses to run without `--user-approved`. Pass the flag only when the user approved that action in this session. A check that reaches a real external or shared system is under the same rule: name it in the preview, run it only with that approval, and say so in the result. A behavior that can be proven only through such a system, and had no approval, is Not verified with that reason.
- **Owned resources.** An action touches only resources this harness created, and says how it decided ownership, or a record the user named for this run, passed by ID with `--user-approved`. It never picks such a record itself and refuses any other.
- **No stand-ins.** Never forge the event, header, or marker the real system would produce, and never call an internal setter or test-only route instead of the real entry point. If the real path refuses, stop and ask.
- **Output.** One JSON object naming the action, the target, and the IDs it created. Exit 0 on success, 2 on refusal or error.

## Checks

A check proves one or more sub-features by driving the real entry point and reading back the result.

- **Read back every side effect.** A success status code is never proof. Read the stored row, the sent message, the written file, or the rendered screen by its exact ID, through reads that follow the Probes rules.
- **Seen versus state.** Say whether the check reads what the user sees or only stored state. A state pass is not a user-visible pass.
- **Report as you go.** A check never writes its evidence file. It appends one event per line to the file `VERIFY_REPORT` names, as each thing happens, so a later crash cannot hide an earlier step: `check`, best first so even a killed run names its check, then `step`, `mark`, `recording`, `created`, and `stopped` events as the Evidence section defines them. Files it keeps, such as a video or a failed step's screenshot, go in the folder `VERIFY_RUN_DIR` names.
- **Run through `vf.py run`.** Run every check, by an agent or a person, as `scripts/framework/vf.py run -- <check command>`, or by sub-feature as `scripts/framework/vf.py verify <id>...`, which runs each named sub-feature's check that way once and prints its status line. It runs the doctor first and stops when the app is not ready, sets those two variables, runs the check from the project root, and builds the evidence file from the events: it records the start and finish times, the code that was on disk and the harness's own code (every file under `scripts/` outside `framework/`, plus any file the command names), neither of which may change during the run, `VERIFY_PLANNED_BREAK` as `planned_break`, and the verdict from the exit code. It accepts the record only when the events follow the Evidence rules and agree with the exit code, stamps it `"accepted_by": "vf.py run"`, builds its replay page, and refreshes `status.md`. A refused record is written as `<time>.json.refused` and doesn't count; fix what the `REFUSED:` lines name and rerun it.
- **Cleanup never touches evidence.** Cleanup removes only what this run created, as the `created` events list it, and never deletes evidence.
- **No verdict without a check.** A run that only observed, or stopped early, reports a `stopped` event and exits 2; its record has `passed: null`. Null is never reported as a pass.
- **Count only fresh events.** A step that waits for an event counts only events that arrived after the step started.
- **Wait for the state.** A step that judges what a page or a polled service shows waits up to one refresh cycle for the expected state, rather than sampling once.
- **Wanted but not built.** A check for behavior the team wants and has not shipped stays in the harness and fails. Report it as Failed with its tracking issue. When it starts passing, the run says so, so the tracking note gets removed. A failing step never stops independent steps after it.
- **Break-tested.** A check counts as proven for a sub-feature only after it failed on a planned break aimed at that sub-feature: a scratch copy with the behavior reverted. Run every break through `scripts/framework/vf.py break run <repo> "<IDs>: <what>" -- python3 scripts/framework/vf.py run -- <check command>`. `vf.py break` copies the code under test, uncommitted changes included, into a scratch worktree, sets `VERIFY_PLANNED_BREAK=<sub-feature IDs, comma-separated>: <what was broken>` so the evidence records what the break aimed at before anyone sees the outcome, saves the edit as `<time>.patch` beside the run's `<time>.json`, outside the run folder so it can be committed with the record, restores the copy afterward, and appends a line to `evidence/breaks.jsonl` for each targeted sub-feature whose judging step failed. Nothing is written in the map: `vf.py status` finds the break in the evidence. A sub-feature with no such break yet may carry `Not break-tested: <reason>.` on its proof line, in the agent's words. While its session is open, `code_state.py` refuses ordinary code recording, including checkout overrides; only the owning harness may record scratch code or end the session. The doctor must still confirm the loaded version; restoring files does not restart processes or undo data changes. The break proves a sub-feature only through the steps judging it that failed; a step that failed only because an earlier one did, such as a receipt step after a payment break, proves nothing about its own sub-feature. The break stands only while the harness code it ran is unchanged: a pass whose `harness_code` differs from the break's for any file the break recorded, or lacks one of them, is not proven until the break is replayed with `vf.py break replay <evidence file>`, which applies the saved patch to the repo the record names. A pass also vouches only for the harness code it ran: once a file in its `harness_code` differs on disk, the behavior is Not verified until its check runs again. Replay it too when a step that caught it is renamed, removed, or stops judging that sub-feature. A step added later needs no new break, but a claim only that step covers stays a noted gap until a break fails it.
- **Steps name what they judge.** In a check that covers several sub-features, each step lists the ones its verdict judges in `sub_features`, and a step that judges none, such as setup, lists none. In a check that covers one, a step that names none judges it.
- **Stable step names.** Keep a step's name the same on every run; values that change, such as IDs, go in `detail`.
- **Exit codes.** 0 passed, and every reported step passed. 1 a step failed. Anything else stopped or could not run; a `stopped` event says why.

## Evidence

Each check run leaves one JSON file, `evidence/<check>/<time>.json`, in a folder named for the check, written by `vf.py run` from the events the check reported. A missing directory or old evidence is a map-check warning, not a setup failure.

The check reports these events, one JSON object per line appended to the `VERIFY_REPORT` file, each with an `event` field:

- `check`: once, anywhere in the report. `name` (the check, used as its folder: letters, digits, dots, dashes, underscores), `sub_features` (the IDs this run claims to prove; leave it out when the check can't know them up front, and `vf.py run` takes the IDs its steps name, or failing that the ones the feature map proves with this exact command, so a run that stops before judging anything is recorded as stopped rather than refused), `reads` (`state`, or what the user sees).
- `step`: `name`, `passed` (true or false), `at`, and optionally `sub_features`, `detail`, `evidence`, and `snapshot` with file names in the run folder.
- `mark`: `kind` (`step` or `action`), `label`, `at`.
- `recording`: once, when the video was kept. `video`, a file name in the run folder, and `starts_at`.
- `created`: lists of IDs by kind, such as `{"event": "created", "orders": ["o_123"]}`; several events merge.
- `stopped`: `reason`, when the run could not reach a verdict.

`vf.py run` adds `code`, `harness_code`, `doctor`, `started_at`, `finished_at`, `planned_break`, `passed`, and `accepted_by`, moves the run folder under `evidence/<check>/<time>/`, and rewrites the file names in `recording` and `snapshot` as paths from `evidence/`. The file it writes:

```json
{
  "check": "checkout-pay",
  "sub_features": ["checkout.pay"],
  "passed": true,
  "reads": "state",
  "code": {"app": {"commit": "a1b2c3d", "branch": "main", "dirty": false, "dirty_hash": null, "on_main": true}},
  "harness_code": {".agents/skills/verify-app/scripts/checks/pay.py": "<sha256>", ".agents/skills/verify-app/scripts/reads.py": "<sha256>"},
  "doctor": {"exit_code": 0, "output": "verify: ready (app a1b2c3d, port 3000)"},
  "started_at": "2026-10-03T14:02:11Z",
  "finished_at": "2026-10-03T14:02:40Z",
  "steps": [
    {"name": "order is paid", "sub_features": ["checkout.pay"], "passed": true, "at": 21.4, "detail": "status=paid", "evidence": {"order_id": "o_123"}}
  ],
  "marks": [
    {"at": 3.0, "kind": "step", "label": "Step 1: Customer pays for the cart"},
    {"at": 4.2, "kind": "action", "label": "Clicks Pay"}
  ],
  "recording": {"video": "checkout-pay/2026-10-03T14-02-11Z/video.webm", "starts_at": 2.1},
  "created": {"orders": ["o_123"]},
  "planned_break": null,
  "stopped": null,
  "accepted_by": "vf.py run"
}
```

`harness_code` is the check's own code as `vf.py run` saw it, hashed with line endings normalized: `settings.md`, every file under `scripts/` apart from its `framework/` folder, and any file the command names. In its `checks/` folder, only the entry the command names counts, a file or a folder, so put each check's entry there and anything two checks share outside it; a command that names no entry gets all of them. A planned break proves a pass only while every file it recorded is unchanged in the pass.

`passed` is `true`, `false`, or `null`, from the check's exit code. `stopped` holds the reason when the run stopped early, from the `stopped` event or the exit code. `created` lists what cleanup may remove. A step's `sub_features` follows the Checks rule above. `planned_break` is null or absent on a run of the code under test; a planned break run records `{"what": "payment capture skipped", "sub_features": ["checkout.pay"], "repo": "app"}`: what and which sub-features from `VERIFY_PLANNED_BREAK`, naming only sub-features the run covers, and the repo of the break session this harness has open. `vf.py run` stops before the check runs when `VERIFY_PLANNED_BREAK` is set and no session is open, or sessions are open on several repos, so a break can't be recorded outside a session. A planned break that names no settings repo proves nothing.

Every run records `started_at` and `finished_at` in UTC to the second, as `2026-10-03T14:02:40Z`, since the latest run decides a behavior's verdict. A passing run has at least one step, every step passed, no `stopped` reason, and no `planned_break`; `vf.py run` refuses a run that exits 0 after a failed step, exits 1 with none, or reports `stopped` and exits 0. Each step has a nonempty unique name and a boolean verdict, and names only sub-features the run covers. Both a pass and its planned break name the same check and record code for every repo in settings. Dirty code requires a valid `dirty_hash`; clean code has no hash. `harness_code` maps each harness file's path from the project root to its SHA-256, and `doctor` is the doctor's result or `"per check"`; a record without a ready doctor proves nothing.

`evidence/breaks.jsonl` is the break ledger: `vf.py break run` appends `{"at", "sub_feature", "check", "what", "step", "evidence"}` for each sub-feature a planned break caught, so a checkout without the break's evidence file can still say when it was broken and what caught it. The evidence file, not the ledger, decides a verdict.

Every `at` is seconds since the check started. Each step records `at`, the moment its verdict was decided. `marks` is the run's timeline: a `step` mark where each numbered step begins and an `action` mark for each thing the run does that a viewer would watch for; a clip of a step runs from its mark to the next `step` mark.

A run that drives a screen records it, keeping the video when the run fails or when its environment sets `VERIFY_KEEP_RECORDING=1`, which is how a person or agent asks for one. Kept files go in the run folder `VERIFY_RUN_DIR` names, which ends up beside the evidence file with the same name: the video, screenshots, console output, failed requests. `recording` names the video, and `starts_at` is when it began, in seconds since the check started. After accepting the record, `vf.py run` runs `scripts/framework/vf.py replay` on it, which builds its replay page and rewrites `recordings.html`, so the page never lags behind the evidence, and for a run that kept its video prints `Recording kept. Watch it at <full path to recordings.html>` so the person who ran it knows where to look. A recording shows what happened; the steps decide the verdict, and a video never stands in for a read.

A failed step in a check that drives a screen names a `snapshot` taken at its verdict, by file names in the run folder: `{"screenshot": "step-3-failed.png", "text": "step-3-failed.txt"}`, where the text is the page's accessibility tree or visible text; the evidence file names them by their paths from `evidence/`. The run's folder keeps console output as `console.json` and failed requests as `requests.json`, each a list of entries with `at` and `text`, kept whether or not the video is.

People and agents read a run differently. A person finds runs and recordings on `recordings.html`, which `scripts/framework/vf.py replay` and `scripts/framework/vf.py clip --steps` rewrite, opens a run's replay page from `scripts/framework/vf.py replay`, and shares a clip from `scripts/framework/vf.py clip --steps`, named for its check, steps, and start time. An agent diagnosing a failure reads the step's detail, its snapshot text, and the console and request entries from the few seconds before its `at`, then looks at stills from `scripts/framework/vf.py clip --frames failed` if those don't explain it; it does not watch the video.

## Reporting

`notes.md` is what people write beside the results: a new limit on what a pass means goes under "Where a pass can mislead", a case nobody could test under "Untested cases".

`status.md` is written by `scripts/framework/vf.py status`, never by hand. Every accepted `vf.py run` refreshes it, so it never lags the evidence. For each sub-feature in the map it writes one line, from the proof line, the accepted evidence, and the Not verified records:

- **Verified:** the latest accepted run of a check covering the sub-feature passed against a ready doctor; the newest accepted planned break of the same check aimed at that sub-feature failed a step judging it; each such step still judges it in the passing run; every harness file the break recorded is unchanged in the pass; both records identify every configured repo; and no Not verified record written after the run stands. The line names the check, what it reads, each repo's commit with the uncommitted-content fingerprint when dirty, the break's date and what it broke, and the evidence file.
- **Failed:** the latest accepted run failed. The line names the step that failed and what it found, the code, the evidence file, and the replay page when the run was recorded.
- **Not verified:** anything else, with the reason: no check yet, unreachable (from the proof line), no run yet, the run stopped, the check is not break-tested (with the proof line's reason when it gives one), the pass is not proven (the run or break record is malformed, the doctor was not ready, a step that caught the break no longer judges it, or the check's code changed since the break), or a standing Not verified record.

When a check could not run, or its pass cannot be trusted, record why with `scripts/framework/vf.py not-verified <id> "<reason>"`: a missing account or entitlement, an OS or external state, a human-only start, a running version that was not the one requested, a skipped entry point (never report it as verified through a different one). The record stands until a later accepted run of a check covering the sub-feature; `--until-break` makes it stand until a later planned break aimed at it as well, for a check whose steps changed. Name the route tried in the reason. `vf.py status` and `vf.py validate` warn about each record still standing, with its age, so a blocker that has quietly cleared gets its check rerun rather than trusted.

```markdown
- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d. Break-tested 2026-10-03: payment capture skipped. Evidence: evidence/checkout-pay/2026-10-03T14-02-40Z.json
- checkout.refund: Not verified. No check yet.
- checkout.retry: Not verified. The sandbox account expired; tried the saved-card route. Recorded 2026-10-21.
```

`scripts/framework/vf.py validate` fails a Verified line that `vf.py status` would not write now, with the reason, and never lets a hand-written Verified line stand. A Verified line whose cited evidence is not on this machine is warned about rather than failed, since a fresh checkout may not carry evidence; `vf.py status` renders what this machine's evidence supports, so run it where the evidence is. After recording results, run `scripts/framework/vf.py validate --require-evidence`, which also fails when a cited evidence file is absent. When a line is wrong, the evidence is wrong or missing: rerun the check, replay the break, record a Not verified reason, or fix the map; never edit evidence or the map to fit a verdict.
