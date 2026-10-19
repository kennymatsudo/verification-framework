---
name: explore-bugs
description: >-
  Run one round of exploratory testing on the running app to find bugs nobody
  wrote down: try one kind of change across several cases on real user flows,
  judge them against invariants written as code, confirm each break (a code
  citation when it is deterministic, reruns and a fresh agent's refutation
  when not), turn it into a failing check, and record the round in a ledger.
  Runs alone or under a loop. Use verify-change to prove a known change and add-tools to add a missing probe or action.
disable-model-invocation: true
---

# Explore bugs

You own one round of exploratory testing: one kind of change across several cases no one wrote down, with each break confirmed. Checks cover the cases someone thought of; this round tests the rest. Each round starts fresh, so the ledger is the only memory: read it first, write it last.

## 1. Check the harness and the app

Find the harness: `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first. If it is missing, stop and name setup-verification. Run its `scripts/framework/validate.py`; if it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop.

The harness needs the invariants module `settings.md` names, with at least three invariants. If the invariants are missing, say so and ask whether to build exploration support now. On yes, load add-feature-checks for exploration setup, then continue here. On no, stop.

Then run, from the project root, the folder holding the skills directory the harness sits in:

- The harness's doctor. The services must run the code you mean to explore. A service on older code may still run a round only when its diff to `HEAD` touches nothing the round drives; name its commit in the report.
- `python3 <this skill's directory>/scripts/ledger.py --harness <harness> summary`.

On the first round of a sweep, if rounds will need the harness's approval-flag actions, name them and get the user's OK. That OK is the approval for those actions during this sweep, and nowhere else.

Stop the round, and a loop running it, when the doctor fails, the last round hit a rate limit or auth error, or the user says the code under the app is being changed. Say what to fix.

Done when the doctor passed and the ledger summary is read, or the round stopped with the reason named.

## 2. Choose the round's cases

Read the harness's known-issue notes and search every connected issue tracker before choosing, so the round does not rediscover an open finding. With no tracker connected, say the tracker was not searched.

Pick one theme for the round:

- Perturbation kinds with the fewest rounds in `kinds_tried` (definitions in `references/perturbations.md`). Pick only what the agent can drive end to end, unless the user says they are present to act.
- When `must_change_approach` is true, a code-reading round: read the recent commits under the code the app runs and its error branches and state transitions, and name inputs that reach branches no check covers.
- Sub-features marked "No check yet" in the harness that a perturbation can now reach.

Search past cases with `ledger.py history <query>` (omit the query for all rounds), then list three to six cases within the theme, each one no check and no ledger row covered. A rerun counts only when the code under it changed since it last passed. If the harness can drive a seeded random walk, a seed no earlier round used is always a new case.

Write each case as "doing X makes Y break", naming the invariant or check that would show it. When the harness cannot drive a case, building that driver as an action through add-tools, or a check through add-feature-checks, is this round's work, and the other cases wait.

Done when every case is written with its check, and the themes not chosen are listed for the report.

## 3. Run them

Run each case once, in the cheapest lane in the harness's `rules.md` that can show its break. Record every resource immediately with `ledger.py created <id> ...`, and record each process's PID as it starts, so an interrupted round leaves its cleanup obligations visible.

Done when every case finished with an evidence path, or stopped with the reason known.

## 4. Judge them

For each case, give every item a verdict of break, lag, lead, or environment:

- Every failed check step.
- Every invariant violation, judged by its kind per the harness's Invariants section.
- Anomalies: error log lines, unexpected 4xx and 5xx responses, browser console errors, missing or doubled events. Each is a lead until it repeats or breaks an invariant.

Write the round's signature: the failed checks, broken invariants, and anomaly kinds, as short stable strings such as `invariant:one-live-session` or `log:timeout-calling-billing`. Novelty is judged by signature, not by recipe.

Done when every case is listed with its verdicts.

## 5. Confirm each break

Skip to step 7 when nothing broke. For each break:

1. Rule out the environment: a dropped tunnel, stale code, a shared resource someone else holds, a quota, or a failure the harness's gotchas already explain.
2. Match it against the known issues read in step 2. Same trigger and same symptom, even through another entry point, is the known issue.
3. Rerun the recipe once on fresh data, with its own evidence.
4. If both runs broke the same way and you can cite the `path:line` that produces the break, it is confirmed, recorded as 2/2 with the citation.
5. Otherwise, such as an intermittent result or no line to cite, rerun until it has run 3 times and record k of n. Then spawn a subagent with a fresh context, on a mid-tier model, with `references/refuter-prompt.md`, and wait for its verdict. Promote the break only when it cannot show the harness, the environment, or a known issue caused it.

Done when every break is promoted, matched to a known issue, or dropped, with the reason.

## 6. Turn each into a check

For each promoted break, add a sub-feature line to its feature file and a check to the harness through add-feature-checks. The check's evidence names that sub-feature. It fails now, and that failure is its proof; its proof line reads `Not break-tested: fails on current code (round <n>).`

Done when each new check runs and fails on the step that shows its break.

## 7. Record the round

- Append the round with `ledger.py add`; `ledger.py add --help` lists its fields and verdicts.
- A failing run keeps what it created for inspection. Once its finding is drafted, matched, or dropped, delete those resources with the harness's cleanup, then record the IDs it deleted with `ledger.py cleaned`, after the round is added.
- Close each open finding whose check now passes on current code, and each open lead this round promoted, matched to a known issue, or dropped, with `ledger.py close <round> ...`.
- Write a draft tracker issue for each promoted finding in the reply. It states the behavior, how to trigger it, the evidence, and the suspected code, marked as a guess. It leaves out the harness and this loop. File it only after the user says yes.

Done when the ledger has the round, the round's processes are stopped, and every resource it created is cleaned or listed in the summary's `to_clean`.

## Calibrating the loop

When the user asks whether the loop works, or the summary shows no `planted` rounds in the last three sweeps and the user agrees, run a calibration round instead. Spawn a subagent on a mid-tier model to pick a planned break from a break-tested line in the harness, apply it in a scratch worktree, and start the app from it, reporting only that the app is ready. Then run a normal round, steps 2 to 5, blind to which break it applied, and compare after. Record kind `planted` with verdict `planted-caught` or `planted-missed`. A loop that misses planted bugs is not evidence of anything.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Never forge a marker the real system would write either; if the real path refuses, stop and ask.

Reply: in the harness's Messages shape, in this order: each case and whether it broke, one line each; each finding with its reproduction rate, evidence path, the check that now covers it, and its draft issue; drivers or invariants added to the harness; coverage (kinds of cases tried, whether any failure was new, and whether the round caught the bug planted to test it); and the next round's suggested case. A round with no findings reports its coverage, never "no bugs found".
