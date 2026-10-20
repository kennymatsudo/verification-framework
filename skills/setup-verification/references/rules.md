# Verification rules

Rules version: 1

Copy this file into the harness as `rules.md`, unchanged; app specifics live in `settings.md`. `scripts/framework/validate.py` fails a copy that differs from the one it ships with. A section applies once the harness has that kind of piece. A piece that cannot follow a rule names the exception in its own help text and in the feature file that uses it.

## Harness layout

Keep framework artifacts at fixed paths relative to this harness; settings cannot move them:

- `README.md`: where a person starts.
- `recordings.html`: each check's latest run and history, for people.
- `settings.md`: app configuration.
- `features/README.md`: feature index.
- `features/requirements.md`: requirement clause map, when needed.
- `status.md`: current results and setup records.
- `tools.md`: command guide.
- `scripts/`: the app's harness tools.
- `scripts/framework/`: framework scripts, copied unchanged.
- `evidence/<check>/`: each check's runs.
- `evidence/doctor/`: saved doctor output.
- `evidence/exploration-ledger.jsonl`: the exploration ledger.

The project root is the folder holding the skills directory this harness sits in: `app/` for `app/.agents/skills/verify-app/`. In a single-repo app it is the repository's top folder; in a monorepo it is the app's own folder. Recipe commands run from it, and `settings.md` paths resolve from it.

Times in file names are UTC with dashes, such as `2026-10-03T14-02-11Z`, so they sort in order and read plainly. Requirements stay in their sources, linked from feature plans and clause maps. Reuse the project's language, clients, and commands, but not its artifact layout.

Setup creates the structure, doctor, and map checker and proves readiness. add-tools builds and proves probes and actions; add-feature-checks builds and proves feature checks. verify-change runs proof on the requested version and delegates missing proof to add-feature-checks within the agreed scope. Existing-checks-only requests prohibit building; unresolved acceptance, missing permissions, and material scope expansion pause dependent work. Evidence retention and Git tracking are the team's choice; skills never edit Git ignore files or delete evidence.

## Feature map

The harness's `features/` directory has one `README.md` index and one file per user-facing feature, in the format below. `scripts/framework/validate.py` enforces it.

### Index: `features/README.md`

  ```markdown
  # <App> feature map

  Open the file for the feature you changed. Follow `../rules.md` for every proof.
  Read [current results](../status.md) for known failures, misleading passes, untested cases, and the latest results.
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

  - checkout.pay: `bin/verify check checkout-pay`. Reads the order row and payment record (state). Break-tested 2026-10-03: payment capture skipped. Evidence: evidence/checkout-pay/2026-10-03T13-55-02Z.json
  - checkout.saved-card: No check yet.
  - checkout.retry: Unreachable: the sandbox processor has no declining test card. Tried the "4000 0000 0000 0002" card.

  ## Gotchas

  - The payment webhook arrives up to 30 seconds after the redirect. Wait on the probe, not a sleep.
  ```

Rules the script enforces:

- Sub-feature lines are `- <id>: <behavior>`. IDs are lowercase, dotted or dashed, and unique across the map.
- Every sub-feature has exactly one line under "How to prove it", in one of three forms: a command in backticks, `No check yet.`, or `Unreachable: <blocker>. Tried <route>.`
- A command line says `Break-tested <date>: <what was broken>. Evidence: <break's evidence file>` or `Not break-tested: <reason>.`
- Every path or command named in backticks under "How to prove it" exists, as a path from the project root. The break's evidence file is a path from this harness, with or without backticks.

Keep the feature file about intended behavior and stable ways to prove it. A current failure, a version-specific pass, or a temporary harness limitation belongs in `status.md`.

Verification plan, Gotchas, and a `## Request flow` section before "How to prove it" (when the code path is not obvious) are optional; leave them out when empty.

### Requirements coverage: `features/requirements.md`

Create this when the project has a requirements source. It holds only links; requirements live in their source, behaviors in feature files.

  ```markdown
  # Requirements coverage

  Source: <link to the requirements document>. Checked <date> against the source as updated <date>.

  ## Clauses

  - A paid order sends one receipt | Launch checklist, row 4 | ids: checkout.pay, checkout.receipt
  - Refunds return to the original card | Launch checklist, row 7 | No check yet
  - Gift cards apply before tax | Pricing design doc, Taxes | not in source
  - Orders over $10k need review | Launch checklist, row 9 | blocked on decision: review threshold
  - Partial refunds | Launch checklist, row 8 | out of scope: phase 1

  ## Conflicts with the source

  - Row 12 asks for a second receipt on refund; `billing/refund.py:88` sends none by design. Proposed edit: "Refunds send no receipt; the order page shows the refund."
  ```

Each clause line is `- <clause> | <source> | <outcome>`, where the outcome is `ids: <sub-feature IDs>`, `No check yet`, `not in source`, `blocked on decision: <decision>`, or `out of scope: <reason>`. `validate.py` checks the form and that every ID exists.

## Verification plan

Before building a proof or running checks, show a preview in the Messages shape: the behaviors in plain words, how the real system will be driven, which observations establish each result and what they do not prove, and links to the requirements, user answers, or acceptance recipes that set the intended behavior. Derive available observations from the real read code, never from the behavior's wording; name an unavailable one as a gap. Keep commands and implementation details secondary.

For a change, include the behaviors it could affect and explain any related behavior included in scope. For a request to check a whole feature, cover its mapped behaviors and disclose unmapped or unchecked gaps. Running every mapped check does not establish complete product coverage.

Proceed when the request and its sources settle the acceptance conditions. When a meaningful one is inferred, conflicting, or unresolved, ask one concise question with a sourced recommendation and wait before building or running the dependent proof. Code explains implementation, not product intent. Action permission is separate from agreement on expected behavior.

Record the agreed plan and its source links in the feature file's Verification plan section. Project acceptance recipes can be a source; the harness owns its proof plan. Compare each check's actions and observations with that plan before trusting it.

Before running a new or materially changed check, spawn a read-only subagent on a mid-tier model for a blind review: give it the agreed plan, its original sources, and the check's files, not the author's reasoning. It compares the check's real entry points, reads, assertions, and exclusions with the plan, and confirms the reads deciding each verdict use no app code. Resolve unsupported assertions, app-code reads, or scope changes before running; ask the user when a finding changes an acceptance condition. The review adds to the planned break, never replaces it.

A passing check and a planned break validate detection only for the agreed claim; an observation alone is not a verdict. Mirror the preview's behavior wording in the final report.

## Tool discovery

Tools are ordinary repo-local commands usable outside verification. Put new harness tools in `scripts/`; reuse existing project commands in recipes when they suffice. Use the project's language, third-party drivers, and connection settings. Python 3 is a fallback for standalone coordination when available. Keep command parsing separate from reusable reads and actions. No MCP server or universal CLI is required.

Document each harness command in `tools.md`: when to use it, what it answers, working directory and inputs, environment prerequisites, permissions and side effects, output and failure meanings, and limits. `--help` works without connecting to services or acting. Redact secrets in help examples and output, and read credentials from the project's connection settings, never from a literal in a tool or the guide. `validate.py` checks each entry's fields, Run from folder, and Help command, and flags a credential written into `tools.md` or `scripts/`; `--run-help` also runs each Help command. A probe's help and guide describe observations, never promise a verified feature.

Link the guide from the project instructions the agent actually loads, scoped to the app in a monorepo. Ask before editing an existing instruction file unless the user authorized that exact edit. Without permission, keep the guide, show the proposed pointer, and report discovery as not wired; never claim unrelated agents can find it. The guide and `--help` must agree.

## Setup

`settings.md` has a Setup Status of `incomplete` or `ready`; incomplete settings may omit unknown required fields. `status.md` has a `## Setup: <harness directory name>` section recording the target, sourced findings, places inspected, blocker, next action, and doctor proof. Run `scripts/framework/validate.py` before live verification: an edited `rules.md`, or one whose Rules version differs from the framework scripts', exits 1 before anything else is checked; incomplete setup exits 2 with its resume action; invalid setup records exit 1. Finish setup with setup-verification before driving the app or claiming coverage.

Ready means setup was proven against the real app, not that the current instance is up; run the doctor every time. Structural validation alone never proves setup.

## Code under test

Every result records the version that produced it. List every repo in `settings.md`, even when there is one. The doctor finds each checkout from its locator and reports the commit the running process actually loaded, not the checkout's current HEAD; a health response that recomputes Git metadata on request is not evidence of loaded code. A missing repo or unreadable running version stops the run.

For each Git repo, record the commit, branch, dirty state, and whether the commit is on its default branch. Dirty means a modified, staged, or untracked file outside the harness directory, and inside the repo's located folder when the locator names a folder within a checkout, such as a monorepo app's own folder; ignored files don't count. Record `dirty_hash` from `code_state.py`: SHA-256 of staged and unstaged diffs and untracked file names, modes, and contents, or null when clean. Capture it with the loaded version at startup; a different hash means different uncommitted code even on the same commit.

Take these from `scripts/framework/code_state.py`, never from Git directly, so every tool means the same by each field; `--checkout` points it at another checkout, and `on_main` is null when the repo has no default branch to compare with. A pass is evidence only for the recorded versions.

## Lanes

Each lane proves more than the one before and costs more. Climb only as far as the claim needs, and name the lane in every result.

| Lane | Who may run it | What it can prove |
| -- | -- | -- |
| 1. Unit | Agent, always | The code's own logic, with external systems mocked |
| 2. Local app | Agent, once the doctor passes | Reads and actions on a local instance, with results read back through probes or the screen |
| 3. Real system | Agent, only with the approval flag | Behavior that crosses a real external or shared system |
| 4. Human action | The user, or an action through the real operator API | What only a person or operator can trigger |

A lane cannot prove a claim about a system it mocks; report the claim Not verified and name the lane that would settle it.

## Doctor

The doctor command in `settings.md` is read-only. It answers one question: is this instance worth driving?

- It reports whether each process is up, which code each one runs, which ports it holds, and whether auth is valid.
- Exit 0 means ready. Exit 1 means not ready, with each reason on its own line. Exit 2 means it could not tell.
- It prints the exact ready line in `settings.md`, which tools may match on. Change the line only together with every tool that matches it.

Start and Stop in `settings.md` pair with it. Stop stops only what Start recorded and removes that launch record; stop an instance the harness started with Stop, never by killing its processes. Start replaces a launch record whose processes have exited, so a crash or reboot never blocks the next start.

## Probes

A probe answers a question about current state: the probe command in `settings.md`, then `<question> <args>`.

- **Read-only.** Database reads run in a read-only transaction. HTTP calls are GET only.
- **One JSON object on stdout.** Concise by default, with `--full` for the raw object.
- **Exit codes.** 0 answered. 1 not found, with `{"not_found": ..., "hint": ...}`. 2 could not answer, with `STOPPED: <reason>` on stderr.
- **Hints.** `next` lists follow-up probe commands. `problems` lists each invariant the current state breaks, with its name and kind. Confirm every entry with the read it names before reporting it.
- **Secrets.** Redact any value whose key looks like a secret, token, or password.
- **Shared reads.** A check that needs the same fact calls the same read function the probe uses, so a probe can re-check any verdict.
- **Read from outside the app.** Read the stored row, the raw response, or the rendered screen directly. A read through the app's models or logic lets the code under test grade itself. A response from the app's own API is still built by its code: a probe that reads one says so in its Limits, and a check judging behavior that endpoint implements reads storage or the outside system instead.

## Invariants

An invariant is a rule that holds whatever happened, written as code in the invariants module named in `settings.md`. It judges any state, including one no check anticipated, so probes, checks, and exploration ask the same question the same way.

- **One function per state it judges,** taking state the caller already read and returning violations, each with the invariant's name, its kind, and a detail. It reads nothing itself and imports no app code.
- **Kinds.** `safety` must hold at every moment: a violation is a break. `eventual` holds once the app settles, by the settle signal in `settings.md`: a violation right after an action may be lag, so recheck after it settles. `lead` is worth a look and wrong only if it repeats or breaks another rule.
- **Missing versus empty.** A value that could not be read is not judged. A value read and found absent is.
- **Break-tested.** Each invariant reports a violation on a planned break, like a check.

## Actions

An action does something a real user or operator would do, through the same entry point they use.

- **Approval flag.** An action with a real or shared side effect refuses to run without `--user-approved`. Pass the flag only when the user approved that action in this session.
- **Owned resources.** An action touches only resources this harness created, and says how it decided ownership, or a record the user named for this run, passed by ID with `--user-approved`. It never picks such a record itself and refuses any other.
- **No stand-ins.** Never forge the event, header, or marker the real system would produce, and never call an internal setter or test-only route instead of the real entry point. If the real path refuses, stop and ask.
- **Output.** One JSON object naming the action, the target, and the IDs it created. Exit 0 on success, 2 on refusal or error.

## Checks

A check proves one or more sub-features by driving the real entry point and reading back the result.

- **Read back every side effect.** A success status code is never proof. Read the stored row, the sent message, the written file, or the rendered screen by its exact ID, through reads that follow the Probes rules.
- **Seen versus state.** Say whether the check reads what the user sees or only stored state. A state pass is not a user-visible pass.
- **Print as you go.** Each step prints its pass or fail as it happens, so a later crash cannot hide it.
- **Evidence before cleanup.** Write the evidence file atomically (temporary file, then rename) before any cleanup. Cleanup removes only what this run created and never deletes evidence.
- **No verdict without a check.** A run that only observed, or stopped early, saves `passed: null`. Null is never reported as a pass.
- **Count only fresh events.** A step that waits for an event counts only events that arrived after the step started.
- **Wait for the state.** A step that judges what a page or a polled service shows waits up to one refresh cycle for the expected state, rather than sampling once.
- **Wanted but not built.** A check for behavior the team wants and has not shipped stays in the harness and fails. Report it as Failed with its tracking issue. When it starts passing, the run says so, so the tracking note gets removed. A failing step never stops independent steps after it.
- **Break-tested.** A check counts as proven for a sub-feature only after it failed on a planned break aimed at that sub-feature: a scratch copy with the behavior reverted. Run every break through `scripts/framework/break_session.py`, which copies the code under test, uncommitted changes included, into a scratch worktree, sets `VERIFY_PLANNED_BREAK=<sub-feature IDs, comma-separated>: <what was broken>` so the evidence records what the break aimed at before anyone sees the outcome, saves the edit as `break.patch` in the run's folder, and restores the copy afterward. While its session is open, `code_state.py` refuses ordinary code recording, including checkout overrides; only the owning harness may record scratch code or end the session. The doctor must still confirm the loaded version; restoring files does not restart processes or undo data changes. Record the break and its evidence file on each targeted sub-feature's proof line. The break proves a sub-feature only through the steps judging it that failed; a step that failed only because an earlier one did, such as a receipt step after a payment break, proves nothing about its own sub-feature. Rerun the break, with `break_session.py replay` on its evidence, if one of those steps is renamed, removed, changed, or stops judging that sub-feature. A step added later needs no new break, but a claim only that step covers stays a noted gap until a break fails it.
- **Steps name what they judge.** In a check that covers several sub-features, each step lists the ones its verdict judges in `sub_features`, and a step that judges none, such as setup, lists none. In a check that covers one, a step that names none judges it.
- **Stable step names.** Keep a step's name the same on every run; values that change, such as IDs, go in `detail`.
- **Exit codes.** 0 passed. 1 a step failed. 2 stopped or could not run.

## Exploration

The explore-bugs skill keeps its round ledger at `evidence/exploration-ledger.jsonl`, beside the evidence it points at.

## Evidence

Each check run writes one JSON file, `evidence/<check>/<time>.json`, in a folder named for the check. Create the folders if absent. A missing directory or old evidence is a map-check warning, not a setup failure.

Use this format:

```json
{
  "check": "checkout-pay",
  "sub_features": ["checkout.pay"],
  "passed": true,
  "reads": "state",
  "code": {"app": {"commit": "a1b2c3d", "branch": "main", "dirty": false, "dirty_hash": null, "on_main": true}},
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
  "stopped": null
}
```

`passed` is `true`, `false`, or `null`. `stopped` holds the reason when the run stopped early. `created` lists what cleanup may remove. A step's `sub_features` follows the Checks rule above. `planned_break` is null or absent on a run of the code under test; a planned break run records `{"what": "payment capture skipped", "sub_features": ["checkout.pay"]}` from `VERIFY_PLANNED_BREAK`, naming only sub-features the run covers.

A passing run has at least one step, every step passed, no `stopped` reason, and no `planned_break`. Each step has a nonempty unique name and a boolean verdict, and names only sub-features the run covers. Both a pass and its planned break name the same check and record code for every repo in settings. Dirty code requires a valid `dirty_hash`; clean code has no hash.

Every `at` is seconds since `started_at`. Each step records `at`, the moment its verdict was decided. `marks` is the run's timeline: a `step` mark where each numbered step begins and an `action` mark for each thing the run does that a viewer would watch for; a clip of a step runs from its mark to the next `step` mark.

A run that drives a screen records it, keeping the video when the run fails or when its environment sets `VERIFY_KEEP_RECORDING=1`, which is how a person or agent asks for one. Kept files go in a folder beside the evidence file with the same name: the video, screenshots, console output, failed requests. `recording` names the video by its path from `evidence/`, and `starts_at` is when it began, in seconds since `started_at`. After writing the evidence file, every run runs `scripts/framework/replay.py` on it, which builds its replay page and rewrites `recordings.html`, so the page never lags behind the evidence. A run that kept its video then prints `Recording kept. Watch it at <full path to recordings.html>` so the person who ran it knows where to look. A recording shows what happened; the steps decide the verdict, and a video never stands in for a read.

A failed step in a check that drives a screen names a `snapshot` taken at its verdict, with paths from `evidence/`: `{"screenshot": "<run>/step-3-failed.png", "text": "<run>/step-3-failed.txt"}`, where the text is the page's accessibility tree or visible text. The run's folder keeps console output as `console.json` and failed requests as `requests.json`, each a list of entries with `at` and `text`, kept whether or not the video is.

People and agents read a run differently. A person finds runs and recordings on `recordings.html`, which `scripts/framework/replay.py` and `scripts/framework/clip.py --steps` rewrite, opens a run's replay page from `scripts/framework/replay.py`, and shares a clip from `scripts/framework/clip.py --steps`, named for its check, steps, and start time. An agent diagnosing a failure reads the step's detail, its snapshot text, and the console and request entries from the few seconds before its `at`, then looks at stills from `scripts/framework/clip.py --frames failed` if those don't explain it; it does not watch the video.

## Messages

A reader faced with a long message tends to approve it unread, so every message makes its point and its ask impossible to miss.

- **Three kinds.** A message is a question, a plan to approve, or a report. A message that only informs, such as `Planned break: <edit>`, is one line and asks nothing.
- **The ask comes last.** A message that needs an answer ends with one short `Needs you:` line, with nothing after it: the question, the recommended answer with its reason or source, and what you'll do next. A skimming reader sees only the last lines, so the question names each thing it asks about and never asks the reader to confirm a list above it: ask only about what the sources leave unsettled. Leaving out a behavior the sources tie to the request is unsettled, so name it in the question rather than only under Gaps. Where a rule came from, and optional next steps, go above that line. Never ask what the project, the harness, or a granted permission already answers. A local, reversible effect, such as local test rows, gets one line in the plan saying so, not a question, and no line in a report; ask before a shared or irreversible one. Hold a question that depends on another's answer; batch independent ones in one picker. For a question with a few known answers, use the session's structured question tool if it has one, recommended answer first; an open question, such as a URL or how the app starts, stays a `Needs you:` line.
- **Once per session.** State a caveat, such as an uncommitted file in the checkout, the first time it matters, and don't repeat it in later messages.
- **Plain words.** Name each behavior by what a user would notice; sub-feature IDs stay in the harness files. Define any other term in a few words, or leave it out. Call the doctor "the readiness check"; the reader doesn't know the harness's internal names.
- **Preview.** Use this shape, leaving out empty lines and any line that would say none. Give one line per behavior; past five, group them by feature with counts. Keep Won't prove to one line, and name each source by its document or file, without line numbers or quotes. The preview is the whole message, with no lead-in and no code fence, and fits in 12 lines.

  ```
  <Verify|Build> <feature or change> on <branch> (<repo> <commit>)

  Will prove: <behavior>
  How: <how the real app is driven>; reads <what is read back>
  Won't prove: <exclusions and unavailable observations>
  Gaps: <behaviors with no proof, and what would be built>
  Sources: <requirements, user answers, or recipes that set the expected behavior>

  Needs you: <question>? I recommend <answer> (<source>). Then I'll <next step>.
  ```

- **Report.** Open with the outcome in one line, and put what went wrong before what passed. Give only what the reader acts on; the skill's `Reply:` line says what that is. A report fits in 12 lines; group behaviors with the same verdict and reason into one line. Versions, tool commands, and evidence paths stay in `status.md` unless that line asks for them. End with nothing, or with a `Needs you:` line that opens with the outcome in a few words, such as `Needs you: all 3 discount behaviors are Verified. Commit them?`, because a skimming reader reads only the end.

## Reporting

Read this harness's `status.md` before a run. Afterward, update it with the exact version tested, outcome, evidence, and any new limit on what a pass means.

Report each sub-feature as one of:

- **Verified:** the check, its lane, the entry point, the evidence file, and the code line.
- **Failed:** the step that failed and what it read, with its replay page when the run kept a recording.
- **Not verified:** why. Name the missing check, or the blocker (account, entitlement, OS, external state, human-only start) and the route tried. Never report a skipped entry point as verified through a different one.

Record each result under `## Latest results` in `status.md` as one line starting with the sub-feature and its verdict. Replace the behavior's earlier line; if duplicate lines remain, the last line is authoritative regardless of evidence timestamps or absent evidence. Keep historical runs outside Latest results. A Verified line names each repo's commit from the evidence and cites the evidence file:

```markdown
- checkout.pay: Verified. scripts/pay, lane 2, checkout API, app a1b2c3d. Evidence: evidence/checkout-pay/2026-10-03T14-02-40Z.json
- checkout.refund: Not verified. No check yet.
```

`scripts/framework/validate.py` fails a current Verified line unless its evidence file has a consistent passing verdict, covers that sub-feature with at least one step judging it, and records every configured repo and the commits the line names. The map's proof must cite a completed planned break of the same check, aimed at that sub-feature, in which a step judging it failed, and each such step must still judge it in the passing run. After recording results, run `scripts/framework/validate.py --require-evidence`, which also fails when a cited evidence file is absent. When a line fails, correct it to what the evidence shows; never edit evidence or the map to fit a verdict.

A run that finds the harness edited outside an add-feature-checks handoff opens its report with `Harness edited during this run: <files>`, before any verdict, and records the diff in `status.md`. Every sub-feature whose check or read changed is Not verified until add-feature-checks re-proves it with a planned break.
