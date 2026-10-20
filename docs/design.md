# Design

This page holds the verification framework's open questions, parked ideas, and decisions. Each decision is an ADR in [`adr/`](adr/), a short record of the problem, the decision, and the options passed on. See [architecture.md](architecture.md) for how the skills, the shared contract, and a harness fit together today.

## Weigh reference projects

A reference project can reveal a missing shared rule or an integration gap, but its layout, commands, and coverage stay local to that project. Recheck it at the version named by each result. Test portability on a different project shape before treating an approach as general.

## Open questions

### Add independent judges where an agent grades its own work

The check reviewer, audit-weak-checks' verifiers, and explore-bugs' refuter and calibration planter are independent judges. Each gets the artifact and the original sources, never the author's reasoning, and is asked to find what's wrong. Two moments still let the author judge itself:

- The agent that wrote a check picks its planned break, so it can pick one the check is sure to catch. A fresh agent that hasn't seen the check could pick the break from the behavior and the code, as explore-bugs' planter does. Test this first on practice repos. Checks that catch their own planned breaks but miss the hidden ones show the author's breaks were too easy.
- An agent changes a check's expectation after it fails. In the pilot, the check reviewer ran once before the first run. When a later failure led the agent to change what the group step expects, no reviewer ran, because `rules.md` doesn't say a changed expectation counts as a materially changed check. Saying so would send the failing evidence and the sources to a fresh reviewer.

Each adds a subagent to every check built, so measure the first before adding it. If both land, write the judge briefing once in `rules.md`.

### Batch planned breaks when runs are expensive

One planned break per behavior means at least two runs per behavior. That is cheap for an app that starts locally in seconds. It isn't when each run spends something scarce: calls to a rate-limited sandbox, paid test transactions, records in a shared system that has a daily quota, or minutes of rebuilding. In the first converted app, each run uses 3 units of a shared daily quota of 100, and each switch to scratch code rebuilds a container for about two minutes. One journey there checks 38 behaviors, so one break per behavior costs 114 units for that journey and about 300 for all 116 checked behaviors, several days of quota. Splitting a journey into one check per behavior doesn't help when nearly every behavior needs the same expensive setup first.

The proposal: one planned break run carries several breaks, each in an unrelated part of the code and aimed at a different behavior. `planned_break` becomes a list of `{what, sub_features}` entries, and [ADR 0017](adr/0017-credit-a-planned-break-only-to-what-it-broke.md)'s rule still applies: a behavior gets credit only where the break was aimed at it and its own step failed. A cheap app keeps one break per run.

Batching has two risks. Masking: one break stops the run before another break's step is reached, which wastes a run but never grants false credit. Interference: two breaks combine so one behavior's step fails because of the other break, which ADR 0017's step labels don't catch. It also changes the `planned_break` and `VERIFY_PLANNED_BREAK` formats, so recorders change again.

Open questions:

- How independent the breaks in a batch must be, and who decides. The check's author already picks its breaks (see "Add independent judges"), and batching also lets it pick which breaks share a run.
- How often masking and interference happen in practice.
- Whether a knock-on failure, which earns no credit, should still be reported, since it may show the check depends on more than its behavior.
- Whether run cost (quota units, money, minutes) belongs in the contract, so skills plan breaks against a budget, or only in settings as a note.

What would settle it: the converted app's break testing done with batching, recording what the runs spent and the masking rate, and a practice repo with hidden breaks in a multi-behavior scenario where every credited behavior's hidden break is also caught.

### Run several planned breaks per session

[ADR 0018](adr/0018-run-planned-breaks-through-a-session-script.md) runs every planned break through a session script. The script already accepts several `run`s between `start` and `end`, but add-feature-checks uses one break per session. On a slow app, switching is most of each break's cost.

In the first converted app, pointing the stack at a new worktree rebuilds a container (about 2 minutes 20 seconds, because its build cache is keyed by the folder path) and restarts a service (about 45 seconds). A run takes about 70 seconds. One break per worktree is about an hour for one feature's 13 behaviors. One worktree for the series would be about 15 to 20 minutes.

The cost is a longer window on scratch code. The open-session guard blocks ordinary code recording, but the developer can't use the stack for other work meanwhile. Batching planned breaks cuts the number of runs, and this cuts the cost of each switch, so the two fit together.

What would settle it: one 13-behavior feature in the first converted app run as one session, timed, with every run's evidence naming its own `break.patch` and fingerprint.

Ending a break run once its targets have failed saves run time on any multi-behavior check. The first converted app does this as a harness choice; whether the framework should support it remains open.

### Support more break-session setups

- A person-only switch: where only a person can point the app at another checkout, `start` and `end` could print the step and wait. Agents run the script without a terminal to wait on, so this needs a resumable shape, such as `start` stopping with the step and a second command confirming it.
- Several repos in one session: a break in one repo with the app running scratch copies of two. Each repo already gets its own session; whether nested sessions work together is untested.
- A service or browser app that starts per check still needs a practice run. `test_break_session.py` proves the CLI workflow.

### Require only the repos a run uses

`code_state.py` stops when any repo `settings.md` lists can't be found, and the doctor treats a missing repo as a stopped run. That is right for a check that runs the repo's code, and wrong for one that doesn't. In the first converted app, browser checks run code from a separate frontend repo, so that repo is listed, and a teammate without a checkout of it can't run even the backend-only checks.

Options:

- Each check names the repos it runs, and evidence records those. This keeps evidence honest per check but adds a field every check must fill.
- A repo line is marked as needed only by some checks.
- The run records a missing repo as absent rather than stopping.

Whatever lands, a Verified line must still name every repo the check ran.

### Let an `env:` locator fall back to the project's default

An `env:` locator reads a checkout path from a project settings file, and finds nothing when the key is absent. Projects often default it in their startup script instead: the first converted app's `make up` falls back to a fixed checkout path when `BACKEND_WORKTREE` is unset. The harness then can't find the checkout the app actually runs, and setup stops until someone writes the default into their settings file.

Options:

- A locator form with a fallback path, such as `env:local-dev/.env:BACKEND_WORKTREE:../backend`. A fallback in settings can drift from the startup script's default.
- Setup asks the developer to set the key.
- The doctor reports the checkout each running process loaded, and code state reads it from there. This is the most faithful but needs every doctor to report it.

### Check the feature map before setup is ready

`validate.py` stops at incomplete setup before it reads the feature map, so map errors stay hidden until readiness is proven. Converting an existing harness is the time map errors pile up, and the readiness proof often waits on a person, such as a login or a stack someone else starts. During the first conversion, the map was checked by calling the validator's functions directly.

Proposed: with setup incomplete, `validate.py` still checks the map and reports its errors, then exits 2 with the blocker. Nothing can be Verified while setup is incomplete, so this checks format only and grants no trust.

### Bring an existing harness into the framework

The first app converted already had a working harness: its own checks, evidence format, results, and skills. The conversion was done by hand: moving tools into `scripts/`, rewriting evidence into the shared format, converting feature files and results, and replacing its skills with the framework's. Its old run history couldn't be carried over, because old evidence lacks fields the format requires, such as each repo's code version.

Setup today assumes a harness is either missing or built by the framework. Options:

- Setup notices an existing harness during discovery and offers a conversion plan.
- A separate skill owns conversion.
- Conversion stays a manual guide.

Old runs could be kept as read-only history in `status.md` rather than converted, which is what the first conversion did. This overlaps "Script the harness copy and upgrade" under Parked ideas, which covers framework-built harnesses only.

### Identify a check's implementation

Planned-break evidence matches a passing run by check identity and stable step names. A changed assertion with the same name still depends on the agent rerunning its break. Before fingerprinting checks, define which reads and invariants belong to the check, how unrelated edits affect proof, and whether content changes invalidate it. This changes what proof remains usable, so settle it in a new ADR before implementation.

### Ask for the requirements source when setup can't find it

audit-coverage's requirements pass runs only when `settings.md` names a requirements source, and nobody is asked for one. Setup's discovery subagent looks and writes `none` when it finds nothing, which is likely when requirements live in a doc or ticket outside the repo. The pass is then skipped on every run. Proposed:

- Setup asks one question when discovery finds nothing: where this app's requirements live, as a link, a file, or none. Only the team knows this, so it meets the "ask only what the project can't answer" bar.
- audit-coverage accepts a link or pasted list for one run, so a user can supply requirements without editing `settings.md`, and offers to save the link.
- A source the session has no tool to open is reported as unread, never treated as empty, matching how skills report a kind of tool with no tool as unsearched.

This changes `settings.md` guidance and setup's questions, so it touches the contract files together. Test the setup question on a practice repo whose requirements sit outside the repo.

### Test the code layout and the moved formats

[ADR 0011](adr/0011-put-each-format-where-its-readers-look.md) moves the feature-map format into `rules.md` and a recommended code layout, drawn from a single Python harness, into add-feature-checks, so add-feature-checks no longer loads setup-verification. Accept it once a TypeScript harness has been built with the layout and it fit without forcing, and a build run in a fresh session never loads setup.

### Test recorded runs on a second app

[ADR 0012](adr/0012-record-runs-and-replay-them-from-evidence.md) proposes recording every check that drives a screen, with a shared replay page and clip tool, drawn from one Python browser harness. Accept it once a harness in another language records a run that replays and cuts cleanly, captions included.

### Test the Stop command on a practice run

[ADR 0013](adr/0013-a-stop-command-beside-start.md) adds a required Stop command beside Start, so anyone can stop an instance the harness started without leaving a launch record that blocks the next start. Accept it once a practice run restarts its app between checks through Stop and every hidden break reaches a verdict.

## Decisions

ADRs 0011, 0012, and 0013 are proposed and wait on the tests under Open questions. The rest are accepted:

- [0001: One harness per app, in a fixed layout, covering every repo it runs on](adr/0001-one-harness-per-app.md)
- [0002: Setup proves readiness and resumes from the harness](adr/0002-setup-proves-readiness-and-resumes.md)
- [0003: Each skill owns one part of verification](adr/0003-each-skill-owns-one-part-of-verification.md)
- [0004: Agree on proof and publish reusable tools](adr/0004-agree-on-proof-and-publish-reusable-tools.md)
- [0005: Drive through the app, judge from outside it](adr/0005-judge-from-outside-the-app.md)
- [0006: Back every Verified with its evidence](adr/0006-back-every-verified-with-its-evidence.md)
- [0007: Messages end with one short ask](adr/0007-messages-end-with-one-short-ask.md)
- [0008: Name skills by a verb, then the question they answer](adr/0008-name-skills-by-verb-and-question.md)
- [0009: Explain why to trust the harness](adr/0009-explain-why-to-trust-the-harness.md)
- [0010: A starting skill that runs the others](adr/0010-a-starting-skill-that-runs-the-others.md)
- [0014: Identify uncommitted code by content](adr/0014-identify-uncommitted-code-by-content.md)
- [0015: A harness layout people can browse](adr/0015-a-harness-layout-people-can-browse.md)
- [0016: Anchor a harness on its project root](adr/0016-anchor-a-harness-on-its-project-root.md)
- [0017: Credit a planned break only to what it broke](adr/0017-credit-a-planned-break-only-to-what-it-broke.md)
- [0018: Run planned breaks through a session script](adr/0018-run-planned-breaks-through-a-session-script.md)
- [0019: A skill that adds tools on their own](adr/0019-a-skill-that-adds-tools-on-their-own.md)
- [0020: A runs page that leads with each check's latest run](adr/0020-a-runs-page-that-leads-with-each-checks-latest-run.md)
- [0021: Check the rules copy](adr/0021-check-the-rules-copy.md)
- [0022: Flag harness edits made during a run](adr/0022-flag-harness-edits-made-during-a-run.md)

## Parked ideas

### Add a test-first playbook

Test-first means writing the check before the code it checks. A verification-framework playbook ([ADR 0010](adr/0010-a-starting-skill-that-runs-the-others.md)) could run add-feature-checks from the requirements before the feature exists, record the checks as wanted but not built, and hand back so the feature gets built in the normal session. It then reruns them with the app's verify skill.

The run before the feature exists works like a planned break, since it's the app with the behavior absent. Check whether `validate.py` accepts a break run on the base commit rather than a scratch copy. That run fails every step for one reason, the missing page or endpoint, so a claim about values, such as a total, still needs a planned break after the build.

Checks written before the code can't be shaped to fit it, which helps with independent judges above. The playbook never writes the feature, so the shared guardrails stay as they are.

### Hide verify-change from the slash menu

Hiding it would make the app's verify skill the one way a person starts verification. Agents still call verify-change. Claude Code supports this in frontmatter. Other agents are unchecked.

### Script the harness copy and upgrade

Setup copies `rules.md` and five scripts unchanged and fills two templates, the same way every run. A setup script that does this would guarantee "unchanged" and shorten setup's step 2.

Nothing updates a harness when the framework changes; `validate.py` only reports a `rules.md` from another version ([ADR 0021](adr/0021-check-the-rules-copy.md)). The pilot was updated by hand. Setup, run on an existing harness, could reuse the same script to refresh `rules.md`, the shared scripts, and the generated verify skill.

### Run checks from a trusted copy

The harness-edit flag ([ADR 0022](adr/0022-flag-harness-edits-made-during-a-run.md)) reports a loosened check after the fact. A fuller defense runs checks from a trusted copy and replays the saved planned break when a check changes, as mutation-testing tools like PIT do. It waits until the flag fires in practice.
