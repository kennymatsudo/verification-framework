# Verification rules

Rules version: 8

Copy this file into the harness as `rules.md`, unchanged; app specifics live in `harness.json`. `scripts/framework/vf.py validate` fails a copy that differs from the one vf last synced, whose hash this harness's `framework.sha256` records with every other framework file's. A section applies once the harness has that kind of piece. A piece that cannot follow a rule names the exception in its own help text and in the feature file that uses it.

## Harness layout

Keep framework artifacts at fixed paths relative to this harness; nothing in the manifest can move them:

- `README.md`: where a person starts.
- `recordings.html`: each check's latest run and history, for people.
- `harness.json`: the manifest, everything a script reads about this app: setup status, requirements source, repos, commands, and tools.
- `features/<slug>.json`: one file per user-facing feature, its behaviors and how each is proven. A `features/<slug>.md` beside it may hold longer prose; scripts ignore it.
- `status.md`: the latest result for every behavior, written by `vf.py status` and never by hand.
- `tools.md`: the command guide, written by `vf.py tools` from the manifest's tools and never by hand.
- `notes.md`: what people write beside the results, as free prose: how the app is started and what needs a person, known failing checks, where a pass can mislead, untested cases.
- `scripts/`: the app's harness tools, with the framework scripts, copied unchanged, in its `framework/` folder.
- `evidence/<check>/`: each check's runs.
- `evidence/doctor/`: saved doctor output.
- `evidence/launch/`: the launch record and output of an instance `vf.py start` started.
- `evidence/not-verified.jsonl`: the Not verified records `vf.py not-verified` writes.
- `evidence/breaks.jsonl`: one line per planned break that caught a behavior, written by `vf.py break run`.

Beside the harness, the same skills directory holds `vf/`: a copy of the framework skill without its `scripts/`, written by `vf.py sync` and recorded in `framework.sha256` with every other framework copy, so a clone of the repo needs no install. Each other skills directory at the project root holds the same copy. Its scripts run from the framework scripts in this harness.

The project root is the folder holding the skills directory this harness sits in: `app/` for `app/.agents/skills/verify-app/`. In a single-repo app it is the repository's top folder; in a monorepo it is the app's own folder. Commands run from it, and the manifest's paths resolve from it.

Times in file names are UTC with dashes, such as `2026-10-03T14-02-11Z`, so they sort in order and read plainly. Requirements stay in their sources, named in each feature's `sources`. Reuse the project's language, clients, and commands, but not its artifact layout.

Evidence retention and Git tracking are the team's choice; skills never edit Git ignore files or delete evidence.

## Feature map

The harness's `features/` folder has one `<slug>.json` per user-facing feature. `scripts/framework/vf.py validate` enforces the format; `vf.py status` lists the behaviors in file-name order.

```json
{
  "name": "Checkout",
  "summary": "A signed-in shopper pays for the items in their cart and sees a confirmation.",
  "reach": ["Cart page, \"Checkout\" button", "POST /api/checkout from the mobile app"],
  "sources": ["launch checklist, row 4 (read 2026-10-03)", "user answer 2026-10-03: an expired saved card is rejected before checkout"],
  "behaviors": {
    "checkout.pay": {
      "words": "paying with a new card creates a paid order",
      "plan": "submit checkout through the real API; read the matching order and payment records. Proves stored payment state, not the confirmation screen.",
      "check": "bin/verify check checkout-pay",
      "reads": "state"
    },
    "checkout.saved-card": {"words": "a returning shopper can pay with a saved card"},
    "checkout.retry": {
      "words": "a declined card shows an error and lets the shopper retry",
      "unreachable": {"blocker": "the sandbox processor has no declining test card", "tried": "the 4000 0000 0000 0002 card"}
    }
  },
  "gotchas": ["The payment webhook arrives up to 30 seconds after the redirect. Wait on the probe, not a sleep."]
}
```

Rules the script enforces:

- `name` and `summary` are non-empty. `reach`, `sources`, and `gotchas` are optional lists of strings.
- Each behavior's key is its ID: lowercase letters, digits, dots, dashes, and underscores, unique across the map. `words` says what a user would notice.
- A behavior has a `check` (a command, run from the project root; a program named by a path must exist) with `reads` (`state`, or what the user sees), or an `unreachable` block with `blocker` and `tried`, or neither, which means no check yet.
- A behavior with a check may name the `repos` its check runs (each a repo in the manifest; absent means every repo) and may carry `not_break_tested`, the reason no planned break has failed it yet. Nothing in the map says Break-tested: `vf.py status` computes that from the evidence.
- `plan` is optional: the agreed proof in a sentence, which the add-checks mode settles before building. The rest is prose for the reader.

Keep a feature file about intended behavior and stable ways to prove it. A current failure, a version-specific pass, or a temporary harness limitation belongs in `status.md`. A journey that crosses several features gets its own file whose behaviors name the per-feature IDs in their words rather than repeating them.

## Tool discovery

Tools are ordinary repo-local commands usable outside verification. Put new harness tools in this harness's `scripts/`, with each check's entry file or folder in its `checks/` folder; reuse existing project commands when they suffice. Use the project's language, third-party drivers, and connection settings. Python 3 is a fallback for standalone coordination when available. Keep command parsing separate from reusable reads and actions. No MCP server or universal CLI is required.

Record each harness command as a tool in `harness.json`: `command`, `use_when` (when to use it and when to use another), `run_from` (a folder relative to the project root; absent means the root), `permissions` (read-only, or the side effects and the approval or ownership rules it enforces), `limits` (what this observation or action does not prove), and optionally `inputs`, `environment`, `result`, and `failure`. `vf.py tools` writes `tools.md` from these entries, and `validate.py` fails a `tools.md` that differs from what it writes now, checks each entry's fields, that `run_from` exists, and that a program the command names by path exists, and flags a credential written into `harness.json` or `scripts/`; `--run-help` also runs each `<command> --help`, which must work without connecting to services or acting. Redact secrets in help examples and output, and read credentials from the project's connection settings, never from a literal in a tool or its entry. A probe's help and entry describe observations, never promise a verified feature.

The entry and `--help` must agree. Project instructions may point at `tools.md`; the skills that build tools own that pointer and ask before editing an instruction file.

## Setup

`harness.json`'s `setup` block has a `status` of `incomplete` or `ready`, the record setup resumes from (`target`, `findings`, `looked_in`), a `blocker` and `next` action (null once ready), and `doctor_proof` (where the doctor's saved output is, with its date and the code it ran on; null until proven). An incomplete manifest may omit unknown required fields. Run `scripts/framework/vf.py validate` before live verification: a `rules.md` that differs from the copy vf last synced exits 1 before anything else is checked; incomplete setup exits 2 with its blocker and next action; an invalid setup block exits 1. Finish setup with vf before driving the app or claiming coverage.

Ready means setup was proven against the real app, not that the current instance is up; run the doctor every time. Structural validation alone never proves setup.

## Code under test

Every result records the version that produced it. List every repo in `harness.json`, even when there is one. A run records the repos the behaviors it proves run: those their entries name in `repos`, or every repo when an entry names none. A repo no behavior in the run names may be absent from the machine; one the run needs that is missing, or an unreadable running version, stops the run. The doctor finds each checkout from `VERIFY_CHECKOUT_<REPO>` and reports the commit the running process actually loaded, not the checkout's current HEAD; a health response that recomputes Git metadata on request is not evidence of loaded code.

For each Git repo, record the commit, branch, dirty state, and whether the commit is on its default branch. Dirty means a modified, staged, or untracked file outside the harness directory and the framework skill copies beside it (those `framework.sha256` records), and inside the repo's located folder when the locator names a folder within a checkout, such as a monorepo app's own folder; ignored files don't count. Record `dirty_hash` from `code_state.py`: SHA-256 of staged and unstaged diffs and untracked file names, modes, and contents, or null when clean. Capture it with the loaded version at startup; a different hash means different uncommitted code even on the same commit.

Take these from `scripts/framework/vf.py code-state`, never from Git directly, so every tool means the same by each field; `--checkout` points it at another checkout, and `on_main` is null when the repo has no default branch to compare with. A pass is evidence only for the recorded versions.

A run that tests code other than the developer's, such as a pull request, makes its own copy with `scripts/framework/vf.py break worktree <repo> <path> <commit> [--branch <name>]`, after any merge it needs, with the merged commit as `<commit>`, so its planned breaks happen there in place. For the repo holding the harness, the harness copy inside the new worktree is the one that runs. For any other repo, run it from that harness copy: it records the worktree as this harness's checkout for the repo, in the project's private Git folder rather than in `harness.json`, so no fingerprint changes. Every command that finds the repo's checkout then uses the worktree and prints a line naming it, and the evidence records the commit it ran. `vf.py break worktree --clear <repo>` goes back to the locator; run it before removing the worktree.

## Doctor

The doctor command in `harness.json` is read-only. It answers one question: is this instance worth driving?

- It reports whether each process is up, which code each one runs, which ports it holds, and whether auth is valid.
- Exit 0 means ready. Exit 1 means not ready, with each reason on its own line. Exit 2 means it could not tell.
- It prints the exact `ready_line` in `harness.json`, which tools may match on. Change the line only together with every tool that matches it.

`scripts/framework/vf.py run` runs it from the project root before every check and stops, running nothing, unless it exits 0; the evidence records its exit code and the end of its output as `doctor`.

`start` and `stop` in `harness.json` pair with it. Start launches the app; it may name a repo's checkout as `{checkout:<repo>}`, which `vf.py` fills with that repo's checkout, and the scratch copy for the repo being broken during a planned break, so the one command both starts the app and points it at the code under test. A `start` of `none` means each check starts the app itself, reading the checkout from `VERIFY_CHECKOUT_<REPO>`; `user` means only a person can start it. Stop stops only what Start recorded and removes that launch record; stop an instance the harness started with Stop, never by killing its processes. Start replaces a launch record whose processes have exited, so a crash or reboot never blocks the next start. `reloads` says whether the app picks up an edit to its checkout without a restart.

`vf.py run`, and the Start, Stop, and Doctor commands, run with `VERIFY_CHECKOUT_<REPO>` set for every repo in `harness.json` (the name in capitals, other characters underscores), naming the checkout the run records for that repo, so a doctor or check that runs the code itself runs the right version.

`scripts/framework/vf.py start`, `stop`, and `doctor` are a launcher a harness may use for these lines when the app runs the checkout's files directly. `start` records every repo's code state and the process it starts, `stop` ends that process and removes the record, and `doctor` is ready only when the process is up, the code on disk still matches the record, and the ready probe it is given exits 0. It knows only what was on disk at start: an app that reloads on edit, runs from a container built from a cache, or compiles before starting needs a doctor that adds its own evidence of the loaded version.

## Probes

A probe answers a question about current state: the `probe` command in `harness.json`, then `<question> <args>`.

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
- **Same run in a break.** A check cleans up when interrupted with SIGINT, as Ctrl-C sends, since `vf.py run` ends a planned break's run that way. It does the same in a planned break as in a pass, so it never reads `VERIFY_PLANNED_BREAK` or `VERIFY_BREAK_SESSION`.
- **No verdict without a check.** A run that only observed, or stopped early, reports a `stopped` event and exits 2; its record has `passed: null`. Null is never reported as a pass.
- **Count only fresh events.** A step that waits for an event counts only events that arrived after the step started.
- **Wait for the state.** A step that judges what a page or a polled service shows waits up to one refresh cycle for the expected state, rather than sampling once.
- **Wanted but not built.** A check for behavior the team wants and has not shipped stays in the harness and fails. Report it as Failed with its tracking issue. When it starts passing, the run says so, so the tracking note gets removed. A failing step never stops independent steps after it.
- **Break-tested.** A check counts as proven for a sub-feature only after it failed on a planned break aimed at that sub-feature: a scratch copy with the behavior reverted. Run every break through `scripts/framework/vf.py break run <repo> "<IDs>: <what>" -- python3 scripts/framework/vf.py run -- <check command>`. `vf.py break start <repo>` opens a session and says where to make the break: in place, in a worktree `vf.py break worktree` made that this harness finds as the repo's checkout and the doctor reports the app running, or else in a scratch worktree holding the code under test, uncommitted changes included. One session can hold every break for a change, one after another. `vf.py break run` sets `VERIFY_PLANNED_BREAK=<sub-feature IDs, comma-separated>: <what was broken>` so the evidence records what the break aimed at before anyone sees the outcome, saves the edit as `<time>.patch` beside the run's `<time>.json`, outside the run folder so it can be committed with the record, restores the product code afterward, and appends a line to `evidence/breaks.jsonl` for each targeted sub-feature it caught cleanly. When the copy's product code or HEAD moved during the restart or the check, it leaves the copy as it is, renames the run's evidence to `<time>.held` so it never counts, and holds the session until `vf.py break end <repo>`, which refuses while the copy's HEAD has moved. Nothing is written in the map: `vf.py status` finds the break in the evidence. A behavior with no such break yet may carry `not_break_tested`, the reason in the agent's words, in its entry. While its session is open, `code_state.py` refuses ordinary code recording, including checkout overrides; only the owning harness may record scratch code or end the session. The doctor must still confirm the loaded version; restoring files does not restart processes or undo data changes. The break proves a sub-feature only through the steps judging it that failed, and only when every step that failed before the first of them judges that same sub-feature. A step that failed only because an earlier one did, such as a receipt step after a payment break, proves nothing about its own sub-feature, even when the break names it as a target. One break therefore credits only the behavior whose step failed first, plus any other target that same step judges; a later behavior needs its own break that the earlier steps pass through. `vf.py run` ends a break's run once every target has a failed step judging it, or once the last step that judged a target in the check's latest pass of the same harness code has passed, with SIGINT to the check's processes and SIGKILL 30 seconds later. A check that outlives a `vf.py run` killed outright is stopped the same way by the next `vf.py break start`, `run`, or `end` on its repo. The break stands only while the harness code it ran is unchanged: a pass whose `harness_code` differs from the break's for any file the break recorded, or lacks one of them, is not proven until the break is replayed with `vf.py break replay <evidence file>`, which applies the saved patch to the repo the record names. A pass also vouches only for the harness code it ran: once a file in its `harness_code` differs on disk, the behavior is Not verified until its check runs again. Replay it too when a step that caught it is renamed, removed, or stops judging that sub-feature. A step added later needs no new break, but a claim only that step covers stays a noted gap until a break fails it.
- **Steps name what they judge.** In a check that covers several sub-features, each step lists the ones its verdict judges in `sub_features`, and a step that judges none, such as setup, lists none. In a check that covers one, a step that names none judges it.
- **Stable step names.** Keep a step's name the same on every run; values that change, such as IDs, go in `detail`.
- **Exit codes.** 0 passed, and every reported step passed. 1 a step failed. Anything else stopped or could not run; a `stopped` event says why.

## Evidence

Each check run leaves one JSON file, `evidence/<check>/<time>.json`, in a folder named for the check, written by `vf.py run` from the events the check reported. A missing directory or old evidence is a map-check warning, not a setup failure.

The check reports these events, one JSON object per line appended to the `VERIFY_REPORT` file, each with an `event` field:

- `check`: once, anywhere in the report. `name` (the check, used as its folder: letters, digits, dots, dashes, underscores), `sub_features` (the IDs this run claims to prove; leave it out when the check can't know them up front, and `vf.py run` takes the IDs its steps name, or failing that the ones whose `check` in the feature map is this exact command, so a run that stops before judging anything is recorded as stopped rather than refused), `reads` (`state`, or what the user sees).
- `step`: `name`, `passed` (true or false), `at`, and optionally `sub_features`, `detail`, `evidence`, and `snapshot` with file names in the run folder.
- `mark`: `kind` (`step` or `action`), `label`, `at`.
- `recording`: once, when the video was kept. `video`, a file name in the run folder, and `starts_at`.
- `created`: lists of IDs by kind, such as `{"event": "created", "orders": ["o_123"]}`; several events merge.
- `stopped`: `reason`, when the run could not reach a verdict.

`vf.py run` adds `code`, `harness_code`, `doctor`, `started_at`, `finished_at`, `planned_break`, `passed`, `accepted_by`, and, on a planned break run it ended, `ended_early`, moves the run folder under `evidence/<check>/<time>/`, and rewrites the file names in `recording` and `snapshot` as paths from `evidence/`. The file it writes:

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

`harness_code` is the check's own code as `vf.py run` saw it, hashed with line endings normalized: `harness.json`, every file under `scripts/` apart from its `framework/` folder, and any file the command names. In its `checks/` folder, only the entry the command names counts, a file or a folder, so put each check's entry there and anything two checks share outside it; a command that names no entry gets all of them. A planned break proves a pass only while every file it recorded is unchanged in the pass.

`passed` is `true`, `false`, or `null`, from the check's exit code. `ended_early` is `{"reason", "killed"}`: why `vf.py run` ended the break's run, and whether the check had to be killed after 30 seconds; that run's `passed` comes from its steps, ignoring its exit code and any `stopped` event it reported while cleaning up, and a record that has it without a `planned_break` is refused. `stopped` holds the reason when the run stopped early, from the `stopped` event or the exit code. `created` lists what cleanup may remove. A step's `sub_features` follows the Checks rule above. `planned_break` is null or absent on a run of the code under test; a planned break run records `{"what": "payment capture skipped", "sub_features": ["checkout.pay"], "repo": "app"}`: what and which sub-features from `VERIFY_PLANNED_BREAK`, naming only sub-features the run covers, and the repo of the break session this harness has open. `vf.py run` stops before the check runs when `VERIFY_PLANNED_BREAK` is set and no session is open, or sessions are open on several repos, so a break can't be recorded outside a session. A planned break that names no manifest repo proves nothing.

Every run records `started_at` and `finished_at` in UTC to the second, as `2026-10-03T14:02:40Z`, since the latest run decides a behavior's verdict. A passing run has at least one step, every step passed, no `stopped` reason, and no `planned_break`; `vf.py run` refuses a run that exits 0 after a failed step, exits 1 with none, or reports `stopped` and exits 0. Each step has a nonempty unique name and a boolean verdict, and names only sub-features the run covers. Both a pass and its planned break name the same check and record code for every repo the behavior's entry names, or every repo in the manifest when it names none; a planned break edited in a repo the behavior does not name proves nothing for it. Dirty code requires a valid `dirty_hash`; clean code has no hash. `harness_code` maps each harness file's path from the project root to its SHA-256, and `doctor` is the doctor's result; a record without a ready doctor proves nothing.

`evidence/breaks.jsonl` is the break ledger: `vf.py break run` appends `{"at", "sub_feature", "check", "what", "step", "evidence"}` for each sub-feature a planned break caught, so a checkout without the break's evidence file can still say when it was broken and what caught it. The evidence file, not the ledger, decides a verdict.

Every `at` is seconds since the check started. Each step records `at`, the moment its verdict was decided. `marks` is the run's timeline: a `step` mark where each numbered step begins and an `action` mark for each thing the run does that a viewer would watch for; a clip of a step runs from its mark to the next `step` mark.

A run that drives a screen records it, keeping the video when the run fails or when its environment sets `VERIFY_KEEP_RECORDING=1`, which is how a person or agent asks for one. Kept files go in the run folder `VERIFY_RUN_DIR` names, which ends up beside the evidence file with the same name: the video, screenshots, console output, failed requests. `recording` names the video, and `starts_at` is when it began, in seconds since the check started. After accepting the record, `vf.py run` runs `scripts/framework/vf.py replay` on it, which builds its replay page and rewrites `recordings.html`, so the page never lags behind the evidence, and for a run that kept its video prints `Recording kept. Watch it at <full path to recordings.html>` so the person who ran it knows where to look. A recording shows what happened; the steps decide the verdict, and a video never stands in for a read.

A failed step in a check that drives a screen names a `snapshot` taken at its verdict, by file names in the run folder: `{"screenshot": "step-3-failed.png", "text": "step-3-failed.txt"}`, where the text is the page's accessibility tree or visible text; the evidence file names them by their paths from `evidence/`. The run's folder keeps console output as `console.json` and failed requests as `requests.json`, each a list of entries with `at` and `text`, kept whether or not the video is.

People and agents read a run differently. A person finds runs and recordings on `recordings.html`, which `scripts/framework/vf.py replay` and `scripts/framework/vf.py clip --steps` rewrite, opens a run's replay page from `scripts/framework/vf.py replay`, and shares a clip from `scripts/framework/vf.py clip --steps`, named for its check, steps, and start time. An agent diagnosing a failure reads the step's detail, its snapshot text, and the console and request entries from the few seconds before its `at`, then looks at stills from `scripts/framework/vf.py clip --frames failed` if those don't explain it; it does not watch the video.

## Reporting

`notes.md` is what people write beside the results: a new limit on what a pass means goes under "Where a pass can mislead", a case nobody could test under "Untested cases".

`status.md` is written by `scripts/framework/vf.py status`, never by hand. Every accepted `vf.py run` refreshes it, so it never lags the evidence. For each behavior in the map it writes one line, from its entry, the accepted evidence, and the Not verified records:

- **Verified:** the latest accepted run of a check covering the behavior passed against a ready doctor; the newest accepted planned break of the same check aimed at that sub-feature failed a step judging it, and every step that failed before it judges that sub-feature too; each such step still judges it in the passing run; every harness file the break recorded is unchanged in the pass; both records identify every repo the behavior's check runs; and no Not verified record written after the run stands. The line names the check, what it reads, each repo's commit with the uncommitted-content fingerprint when dirty, the break's date and what it broke, and the evidence file.
- **Failed:** the latest accepted run failed. The line names the step that failed and what it found, the code, the evidence file, and the replay page when the run was recorded.
- **Not verified:** anything else, with the reason: no check yet, unreachable (from its entry), no run yet, the run stopped, the check is not break-tested (with the entry's reason when it gives one), the pass is not proven (the run or break record is malformed, the doctor was not ready, a step that caught the break no longer judges it, or the check's code changed since the break), or a standing Not verified record.

When a check could not run, or its pass cannot be trusted, record why with `scripts/framework/vf.py not-verified <id> "<reason>"`: a missing account or entitlement, an OS or external state, a human-only start, a running version that was not the one requested, a skipped entry point (never report it as verified through a different one). The record stands until a later accepted run of a check covering the sub-feature; `--until-break` makes it stand until a later planned break aimed at it as well, for a check whose steps changed. Name the route tried in the reason. `vf.py status` and `vf.py validate` warn about each record still standing, with its age, so a blocker that has quietly cleared gets its check rerun rather than trusted.

```markdown
- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d. Break-tested 2026-10-03: payment capture skipped. Evidence: evidence/checkout-pay/2026-10-03T14-02-40Z.json
- checkout.refund: Not verified. No check yet.
- checkout.retry: Not verified. The sandbox account expired; tried the saved-card route. Recorded 2026-10-21.
```

`scripts/framework/vf.py validate` fails a Verified line that `vf.py status` would not write now, with the reason, and never lets a hand-written Verified line stand. A Verified line whose cited evidence is not on this machine is warned about rather than failed, since a fresh checkout may not carry evidence; `vf.py status` renders what this machine's evidence supports, so run it where the evidence is. After recording results, run `scripts/framework/vf.py validate --require-evidence`, which also fails when a cited evidence file is absent. When a line is wrong, the evidence is wrong or missing: rerun the check, replay the break, record a Not verified reason, or fix the map; never edit evidence or the map to fit a verdict.
