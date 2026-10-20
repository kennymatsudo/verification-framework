---
name: verify-pr
description: >-
  Verify a teammate's pull request, or several across repos that make one
  change, with the repo's end-to-end harness: list every fix and test case
  the PRs claim, plus changes their code makes that the descriptions leave
  out, decide with the developer which belong in the harness, build only
  those checks on a branch of their own, run them on the PRs' code together,
  sort each failure into PR defect, already tracked, harness problem, or
  flake, and draft a PR comment of what passed, what failed, and what went
  untested, with a short demo video of the changed behavior. Use for "verify
  PR #123", "verify these frontend and backend PRs together", "run our
  scenarios on PR #123", "which of this PR's test cases belong in the
  harness". Use review-pr to find defects by reading the code.
disable-model-invocation: true
---

# Verify a pull request with the harness

You own two answers for one change, made by one teammate's pull request or by several across repos (a frontend and a backend PR, say): which of its claims the harness should guard, and whether the PRs deliver them together on the real stack. With several PRs, treat them as one change throughout: one claim list, one set of runs, one result. The harness is the expensive layer, so a claim earns a check only when nothing smaller can see it.

The harness is the repo's end-to-end verification layer: one setup-verification built (`verify-*/rules.md` in a skills directory), or else the harness the repo's agent instructions name. If neither exists, stop and say so. Read its rules, its settings, and its run instructions (lanes, the stack check, which actions need the developer's OK, evidence, cleanup) before the first run.

For a framework harness, run its `scripts/framework/validate.py` first; if it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop.

## 1. List the claims

Read each PR's title, description, changed files, and head commit from the code host. List every fix or test case each claims, using the PR's own section names and numbers, plus anything it says it moved to another ticket.

The description may be incomplete, especially when it was generated from the diff, so build the list from two more sources:

- **The ticket.** For each ticket the PR links, read its acceptance criteria from a session tool that can search the ticket tracker, and add any criterion the description doesn't cover, marked as from the ticket. Note each place the ticket and the description disagree. With no such tool, say the ticket was unsearched.
- **The diff.** Read the changed code and add each change in behavior a user could notice that neither the description nor the ticket mentions, marked as found in the code. Leave out refactors, renames, and changes no user could notice.

Done when every claim in each description, every uncovered ticket criterion, and every unmentioned user-visible change in each diff is on the list, each marked with its source and PR, and the list names each PR's head commit.

## 2. Gate each claim

Read the harness's current coverage: its feature or scenario docs, and the open findings and untested cases in its chosen results home. Then give every claim on the list one verdict:

- **Add**: the outcome depends on two or more services or components agreeing, or on real timing between them (a poll, a webhook, a send in flight), and no current check proves it. Name the components, and the break the check would catch that no single component's own tests could. If you can only name a break inside one component, the claim is a Skip, even when reaching the situation takes several services.
- **Already covered**: a current check proves it. Name the check with its `file:line` and plan to rerun it on the PR's build. When it covers only part of the claim, say which part and gate the rest. Before saying no check covers something, search the check code for it.
- **Add with a missing step**: it belongs, but no current step reaches the situation. Name the step to build, and build it now if the developer agrees, rather than deferring.
- **Skip**: one component's code decides the outcome, even when the harness could drive it, so the PR's own unit tests are its home; or the harness would have to fake the very failure it tests.

A check for behavior the PR does not deliver yet still goes in now and fails until it does, but only when it names the ticket or pull request that will make it pass, and it reports when it starts passing so that note gets removed.

Open with one line giving how many checks the list adds and why. Then give one line per claim in the PR's order, with ticket and code claims after the PR's own, their source in parentheses. Start each line with its verdict so a reader can scan down the left edge, then the claim's name in plain words, then a short reason. For each Add, the line also says where it lands and what it costs to run (time, shared resources, side effects); for each Already covered, the check and what its rerun costs. When more than five claims share a verdict and reason, put them on one line with their count. Under **Worth knowing**, give each place a ticket and the description disagree, one line each. End with a single `Needs you:` line asking the developer to approve the list, with how many checks it adds, which reruns it includes, and the shared resources and side effects they use; fold any other open choice into that line with its recommended answer. Approving it is the go-ahead for exactly the runs and side effects it names.

Done when every claim has a verdict and a reason, and the developer has approved the list.

## 3. Check out the change

Make one git worktree per PR at its head commit, beside that repo's checkout, so the developer's own checkouts stay untouched. The repo holding the harness also gets one, on a new branch `verify-pr/<PR number>-checks`: off its PR's head when one of the PRs is in that repo, otherwise off its default branch. Checks are built there and the harness runs from there. Point the stack at the worktrees as the harness's docs say (in a framework harness, its `Run scratch code` setting). A repo the harness runs that no PR touches stays at its default branch; note it for the report. Record every worktree you make, for the hand-off.

Done when each PR has a worktree at its head commit, the checks branch exists, and the developer's own checkouts are unchanged.

## 4. Build the approved checks

For a framework harness, load add-feature-checks with the approved claims, acceptance sources, and action permissions to build and prove only those checks. For a non-framework harness, build only what was approved in its existing scenarios and drivers, with unit tests beside them, following its own conventions. A check of what a page or a polled service shows waits up to one refresh cycle for the expected state rather than sampling once. Update every doc that describes the changed scenarios.

Done when the unit suite passes and each new check fails with its behavior reverted, using the cheapest proof the harness allows (add-feature-checks's planned break for a framework harness).

## 5. Run on the PRs' code

Run the approved scenarios with every PR's code loaded at once. In a framework harness, set `VERIFY_KEEP_RECORDING=1` for each check that drives a screen and covers a changed behavior, so a passing run keeps the video for the demo without a rerun. Before handing any step to the developer as one only they can run, read the command's script: a step needs them only when it prompts, needs their login or credentials, or has a side effect they have not approved. Run everything else yourself.

Confirm each run's evidence names every PR's head commit and any other component versions it depended on. Decide reruns from the evidence: rerun only when it points to a stack or harness cause, and report every rerun. A failed product check may already have enough evidence to compare with the base build.

Done when each approved scenario has finished on every PR's head commit, and every service is back where it started.

## 6. Sort each failure

For every failed check, decide one:

- **PR defect**: a regression; the same check passes on the base build (a comparable recorded result, or a base run) and fails on the PR's build. Run the base only for failures. The comparison must use equivalent entry points and external conditions. With several PRs, the base build is every repo at its PR's base.
- **Already tracked**: the failure is an open finding in the project's results home or a ticket the PR names.
- **Harness problem**: the screenshot, trace, or stored state shows the product did the right thing, and the check judged it wrong. Fix the check, say so, and do not count the run as evidence for that claim.
- **Flake or stack problem**: a rerun disagrees, or the run never reached the claim (a redirect, a stopped service, a stale checkout). Its later checks are void. The same flake twice is a harness problem until its cause is found: add the diagnostic that would name the cause before retrying again.
- **Unresolved**: the check failed on the PR, but a comparable base result is unavailable and the evidence cannot place it in the other categories. Name the base check needed.

Done when every failure has one verdict with the evidence that decided it.

## 7. Report

Update the harness's chosen results home, if it has one: a results row for the PR's commit, and the open findings and untested cases the run changed. In a framework harness, write result lines as its rules' Reporting section defines and run `scripts/framework/validate.py --require-evidence`. Draft the PR comment for an author who will skim it. Call claims what the PR calls them (its test plan, test cases, or fixes), never "claims", and keep it to one screen with the detail blocks collapsed:

- A `Tested with Verification Framework` heading, then a bold count of problems found, passed, and not tested end to end. One line follows with the commit, the other component versions and whether they ran together on one stack (with several PRs: each PR by link with the commit it ran on, and that a new commit on any of them makes this result stale), the features covered by name, how many of the PR's items that covers, and how many changes were found in the code or ticket beyond them.
- **Failed on this PR**, **Failed, tracked elsewhere**, **Unresolved failure**, **Passed**, and **Not tested end to end**, in that order, leaving out empty sections. Each item gets one line saying what was tested in terms of what the user sees, with no section numbers or labels, since most PRs don't number their items and a reader can't look a label up. A PR defect names the base result it was compared with. An unresolved failure names the base check needed. A "not tested" line says what was not proven and why in a few words, not that a run failed.
- Under each item in **Failed on this PR** and **Passed**, a collapsed `How it was checked` block: what it did, what it saw at each place it looked, and the break it was shown to fail on. Leave out evidence paths: they point at files on the developer's machine that readers can't open. This is how the author judges whether it was tested the way they meant.
- Under **Worth knowing**: anything the PR changes that a reader would not expect, each place the ticket and the description disagree, and a ticket left unsearched.

With several PRs, the same comment goes on each one.

**Demo.** In a framework harness, when a check that covers a changed behavior drives a screen and passed with its video kept, cut a demo. List the run's steps with `<harness>/scripts/framework/clip.py <evidence file>` and pick the fewest consecutive steps that show the changed behavior and its result, leaving out sign-in, setup, and steps the PR didn't change. Cut them with `clip.py <evidence file> --steps <range> --demo`: no captions, still waits cut short, the result held on screen. Read stills of each picked step (`--frames <step>`) for anything that shouldn't be public, such as real customer data, secrets, or internal addresses, and cut a different range or skip the demo if one shows. If `clip.py --check` says this machine can't make clips, give its install line instead; never install it unasked. Show the picked steps with a one-line reason each, and the demo's path. The demo goes on the PR that changes the screen, attached through the code host's upload when its tools have one, or else handed to the developer to attach; the other PRs' comments link to it.

Show the draft, ending with `Needs you:` to post it with its demo. Post or edit the comments only when the developer says to, then link them.

Done when the results home is updated, if one exists, the demo is cut or its absence explained, and the comments are drafted or posted on the developer's word.

## 8. Hand off

Offer, in one question, the two follow-ups: open a pull request for the new checks from the checks branch, and remove the worktrees this run made. The checks PR targets the PR in the harness's repo when there is one, so the checks merge with the code they test; otherwise it targets the default branch and says to merge it after every PR it names. Never push to a teammate's branch. Removing a worktree deletes only that checkout; say that the checks branch stays and whether it has been pushed. Before removing the harness worktree, commit its checks to the branch or list the uncommitted files that would be lost and get a yes. Remove each with `git worktree remove`, and confirm `git worktree list` no longer shows it.

Done when the developer has answered, and each follow-up they chose is done.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.

Reply: one line on the outcome first, then each claim's result in plain words with the commits it ran on. Then Details: the gate list with each verdict, the checks built and their branch, every rerun, the shared resources the runs used, the demo's steps and path, and the worktrees made. End with the PR comments' links and `Needs you:` for the hand-off, or `Needs you:` to post the draft.
