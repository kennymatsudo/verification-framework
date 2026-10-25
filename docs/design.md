# Design

Open questions, parked ideas, and decisions. Each decision is an ADR in [`adr/`](adr/): a short record of the problem, the decision, and the options passed on. [architecture.md](architecture.md) describes how things fit together today.

A reference project can reveal a missing shared rule or an integration gap, but its layout, commands, and coverage stay local to it. Test an approach on a different project shape before treating it as general.

## Open questions

### Add independent judges where an agent grades its own work

The check reviewer and the weak-checks verifiers are independent judges: each gets the artifact and the sources, never the author's reasoning. One moment still lets the author judge itself: **the author picks its own planned break**, so it can pick one the check is sure to catch. A fresh agent that hasn't seen the check could pick the break from the behavior and the code. Checks that catch their own breaks but miss hidden ones would show the author's breaks were too easy. It adds a subagent to every check built, so measure it on practice repos first.

A change to a check after its review, including an expectation changed after a failed run, now goes back for review as a diff before the next run, to the same reviewer when the session can resume it (vf-verify's `references/verification-plan.md`).

### Batch planned breaks when runs are expensive

One planned break per behavior means at least two runs per behavior. That's cheap when the app starts in seconds. It isn't when each run spends something scarce: a rate-limited sandbox, paid test transactions, a shared daily quota, or minutes of rebuilding. In the first converted app (an existing harness brought into the framework by hand, see below), one journey checks 38 behaviors, and one break per behavior would cost several days of quota.

**Proposal:** one break run carries several breaks, each in an unrelated part of the code and aimed at a different behavior. `planned_break` becomes a list of `{what, sub_features}` entries. [ADR 0005](adr/0005-credit-a-planned-break-only-to-what-it-broke.md)'s rule still applies: a behavior gets credit only where the break was aimed at it and its own step failed.

**Risks:** masking (one break stops the run before another's step is reached, which wastes a run but never grants false credit) and interference (two breaks combine so a step fails for the wrong reason, which step labels don't catch). It also changes the `planned_break` and `VERIFY_PLANNED_BREAK` formats.

**Still open:** how independent the breaks must be and who decides; how often masking and interference happen; whether a knock-on failure should be reported even though it earns no credit; whether run cost belongs in the contract or only in settings.

**What settles it:** the converted app's break testing done with batching, with the runs spent and the masking rate recorded, plus a practice repo with hidden breaks where every credited behavior's hidden break is also caught.

### Run several planned breaks per session

`break_session.py` already accepts several `run`s between `start` and `end`, but the add-checks mode uses one break per session. On a slow app, switching is most of each break's cost: in the first converted app, a 13-behavior feature takes about an hour with a fresh worktree per break, and would take 15 to 20 minutes with one worktree for the whole series.

The cost is a longer window on scratch code, during which the developer can't use the stack. This fits with batching above: one cuts the number of runs, the other the cost of each switch.

**What settles it:** one 13-behavior feature run as one session, timed, with every run's evidence naming its own saved patch and fingerprint.

### Support more break-session setups

- **A person-only switch.** Where only a person can point the app at another checkout, `start` and `end` could print the step for the person to do and exit, and a second command could record that it was done. Agents have no terminal to wait on, so the script can't simply pause.
- **Several repos in one session.** Decided: repos in one Git checkout share one session, named for the repo `break start` was given; a break run with sessions open on two separate checkouts still stops, since a break names one repo.
- **An app that starts per check** still needs a practice run. The eval suite's `relay` practice repo (a command-line tool with no server) avoids `per check` instead: its doctor writes a pointer file naming the checkout the checks run the command from, `Run scratch code` repoints it, and `After an edit` is `reloads`, so planned breaks run through the normal session. Whether that pattern should replace `per check` in the settings template is open.

### Require only the repos a run uses

`code_state.py` stops when any repo in `settings.md` can't be found. That's right for a check that runs the repo's code and wrong for one that doesn't. In the first converted app, a teammate without the frontend repo can't run even the backend-only checks.

**Options:** each check names the repos it runs; a repo line is marked as needed only by some checks; or the run records a missing repo as absent. Whatever lands, a Verified line must still name every repo the check ran.

### Let an `env:` repository location fall back to the project's default

An `env:` repository location in `settings.md` reads a checkout path from a project settings file and finds nothing when the key is absent, even though the startup script defaults it. Setup then stops until someone writes the default into their settings file.

**Options:** a location form with a fallback path (which can drift from the script's default); setup asks the developer to set the key; or the doctor reports the checkout each process loaded and code state reads it from there (most faithful, but every doctor must report it).

### Check the feature map before setup is ready

`validate.py` stops at incomplete setup before reading the feature map, so map errors stay hidden until readiness is proven. Converting an existing harness is when map errors pile up, and readiness often waits on a person.

**Proposal:** with setup incomplete, `validate.py` still checks the map and reports its errors, then exits 2 with the blocker. This checks format only and grants no trust.

### Bring an existing harness into the framework

The first converted app already had checks, an evidence format, and skills of its own. Conversion was done by hand, and old run history couldn't carry over because it lacked required fields.

**Options:** setup notices an existing harness and offers a conversion plan; a separate skill owns conversion; or conversion stays a manual guide. Old runs can stay as read-only history in `status.md`.

### Ask for the requirements source when setup can't find it

Setup's discovery writes `none` as the requirements source when it finds nothing in the repo, and nobody is asked. Requirements often live in a doc or ticket outside the repo.

**Proposal:** setup asks one question when discovery finds nothing: where this app's requirements live, as a link, a file, or none. A source the session has no tool to open is reported as unread, never treated as empty. Test on a practice repo whose requirements sit outside it.

### Prove at setup that the harness runs from a second checkout

The verify-pr mode builds checks in a worktree of the harness's repo, so the developer can keep editing their own checkout while a run that can take hours goes on. That only works if the harness can see the running app from the worktree, and it often can't: the app keeps state in files Git ignores, which a fresh worktree doesn't have. In the first converted app, the stack's settings, process records, and logs live under the harness repo, so the doctor in a fresh worktree reported not ready, and the agent built in the developer's checkout instead. A practice repo with a database file created by its start command has the same gap. Today the agent meets this mid-run and has to ask a question the developer can rarely answer on the spot.

Linking the ignored folders into the worktree made the first converted app's doctor report ready. But Git listed the links as untracked, because its ignore patterns (`pids/`) match only real folders, so every run would record the harness repo as having uncommitted code.

**Proposal:** setup proves this once, alongside readiness. It runs the doctor from a throwaway worktree. If that fails, it finds the ignored state the doctor needs, proposes links, confirms Git doesn't see them as changes (naming any ignore-file fix for the developer to make, since skills don't edit ignore files), and records the result in `settings.md`: the paths a worktree links, or that the harness runs only in place. Verify-pr then uses a worktree when settings says it works, and otherwise tells the developer up front which checkout the run uses and to leave it alone until the run ends.

**Costs:** a new settings blank and setup step, so the template, `validate.py`, USAGE.md, and `docs/internals.md` change together and the Rules version rises. One more thing setup asks the developer to approve.

**Still open:** whether commands that restart the app (`Run scratch code`) work from a linked worktree, which is untested; whether links or copies suit each kind of state (links share state the app writes, copies freeze a snapshot); whether planned-break scratch copies need the same list.

**What settles it:** the first converted app running one verify-pr from a linked worktree, with clean code state in its evidence and a restart through `Run scratch code`, plus a second app whose stack runs outside its repo, where a worktree needs no links.

### Exercise three pieces on a second app

Three parts of the contract came from one Python harness and haven't run anywhere else:

- The recommended code layout in the add-checks mode. Settled once a TypeScript harness fits it without forcing.
- Recorded runs, the replay page, and the clip tool. Settled once a harness in another language records a run that replays and cuts cleanly.
- The required Stop command. Settled once a practice run restarts its app between checks and every hidden break reaches a verdict.

## Decisions

- [0001: One harness per app, in a fixed layout, anchored on its project root](adr/0001-one-harness-per-app.md)
- [0002: Three skills: one for people, one for agents, one that explains](adr/0002-three-skills.md)
- [0003: Agree on proof before building it, and end every message with one short ask](adr/0003-agree-on-proof-and-end-with-one-short-ask.md)
- [0004: Drive through the app, judge from outside it, and compute every verdict from the evidence](adr/0004-judge-from-outside-and-compute-verdicts-from-evidence.md)
- [0005: A planned break proves only what it broke, run in a scratch copy of a fingerprinted check](adr/0005-credit-a-planned-break-only-to-what-it-broke.md)
- [0006: One versioned tool writes every record](adr/0006-one-versioned-tool-writes-every-record.md)
- [0007: The framework ships inside the app's repo](adr/0007-the-framework-ships-inside-the-app-repo.md)
- [0008: Fingerprint what a check could load, not the whole harness](adr/0008-fingerprint-what-a-check-could-load.md)
- [0009: A planned break names its repo, and its edit travels with the record](adr/0009-a-break-names-its-repo-and-its-edit-travels-with-the-record.md)

## Parked ideas

Four pieces shipped before this redesign (commit f220499 on main) and were removed before any app used them. Each is still in that tree:

- **Exploratory testing with invariants.** Rounds of one kind of change on the real app, judged by always-true rules written as code. Pick it up when a team wants bug-hunting beyond its known behaviors and has three invariants worth writing.
- **A requirements coverage map.** A clause-by-clause map from a written spec to behaviors. Pick it up when a project needs to show every clause has a check.
- **Captioned clips.** A caption bar naming the step under each clip. Pick it up if reviewers can't follow an uncaptioned clip.
- **Lanes.** Four levels of proof named in every result. The one fact that mattered, approval for a real system, now lives under Actions in `rules.md`.

A redesign review on 2026-10-21 set these aside:

- **Readiness proven by `vf.py`.** The doctor already runs before every verification, and the up/down proof is a procedure in vf's `references/doctor.md`. Pick it up if a harness is ever marked ready without the doctor having run.
- **Breaks in the developer's checkout** instead of a scratch worktree. Rejected: a crash or a second agent could lose uncommitted work. The rebuild cost it aimed at is better met by one persistent worktree per repo, which is still open.
- **A single packed `vf.pyz` with no `rules.md` copy.** Rejected: an archive can't be reviewed in a diff, and the rules copy is what reviewers and vf-explain read.
- **Blind breaks in place of the weak-checks audit.** Worth adding beside the audit's scripts, not instead of them. This is the independent-judges question above.

Three smaller ideas, not yet weighed:

- **A test-first playbook.** Run the add-checks mode from the requirements before the feature exists, record the checks as wanted but not built, and rerun them after the build. The run before the feature exists works like a planned break, but a claim about values still needs one after the build.
- **Hide vf-verify from the slash menu**, so the app's verify skill is the one way a person starts verification. Claude Code supports this in frontmatter; other agents are unchecked.
- **Refresh the generated verify skill on sync.** `vf.py sync` replaces the rules and scripts but nothing refreshes `verify-<app>/SKILL.md` when its template changes.
