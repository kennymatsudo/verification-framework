# Weak-checks mode

Follow this when vf runs in audit mode for weak checks. The Guardrails in vf's `SKILL.md` apply throughout.

You own one answer: would each check in this harness go red if the behavior it guards broke? A vacuous check that cannot fail, and a unit test that passes one, are the worst outcomes here: every run then reports a pass nobody earned.

The harness is the repo's end-to-end verification layer: one vf built (`verify-*/rules.md` in a skills directory), or else the harness the repo's agent instructions name. If neither exists, stop and say so. Never run live scenarios or touch shared or production systems; a claim only a live run can settle goes to the developer as a named scenario and break to run.

## 1. Gather the hard facts

From the harness's docs and agent instructions, find where its check code and unit tests live, the unit suite command, how checks are named, the rules it promises (the harness's `rules.md`, or its trust or verification doc), any coverage map or status file, and the docs and skills that tell agents what counts as proof. Use those names in every command below.

For a harness vf built: Run `<harness>/scripts/framework/vf.py validate --written-for 1` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. If it reports an edited `rules.md` or one from another framework version, stop: the rules the audit would hold checks to are not the framework's. Any other error is a lead for the finders.

Then run, in parallel where possible, keeping each output:

- The unit suite. If it fails, stop and report the failing tests; an audit of a red suite measures nothing.
- For Python check code, the three audit scripts, from `<harness>/scripts/framework/` for a harness vf built and otherwise from the installed vf's `scripts/`. Run them; read their `--help` only for flags.
  - `break_checks.py --harness <dir> --suite "<suite command>" --match "<check name regex>"`. In a scratch copy, it stubs each check function to return its all-clear value and runs the suite. `SURVIVED` means no unit test can tell that check from a broken one. Add `--copy <path>` for anything else the suite imports.
  - `smells.py <dirs>`: leads for tests with no assertion, existence-only assertions, self-comparisons, skips, and broad excepts that swallow a failure.
  - `weakened.py --path <dir> --match "<regex>"`: every deleted test, removed assertion, new skip, and changed check since the last `Audit harness checks` commit, else 30 days.
- For other languages, do the same by hand: the repo's mutation tool scoped to the check functions if it has one, else the same all-clear stubs, and `git diff` since the last audit for removed assertions and new skips.
- Every probe and scenario runner's `--help`, for the commands and names that exist today.

Done when `vf.py validate` passed its rules and setup checks for a framework harness, the suite is green, and you hold each output, or the reason one could not run.

## 2. Find, in parallel

Split the harness into slices: one per feature area with its checks and their unit tests, one for UI drivers, one for the probe and read layer, and one for the verification docs and skills. Spawn one read-only finder per slice, on a mid-tier model, with the prompt in `references/finder.md` and the rubric in `references/rubric.md`. Give each finder the step 1 lines that fall in its slice. Every `SURVIVED` check and every `weakened.py` lead must come back with a finding or a reason it is fine.

Done when every slice is listed with its finder's return, and every finding has a `file:line`, quoted code, a rubric ID, and a "passes even when ... because ..." line. Drop any finding without one.

## 3. Verify, independently

Spawn verifiers on a mid-tier model with `references/verifier.md`, batching findings by slice. A verifier gets each finding's location, claim, and failure scenario, never the finder's reasoning, so the review is blind; a finder wants its finding to be real. Each finding returns `CONFIRMED` with the command and output that show the check staying green while broken, `REFUTED` with the code that defeats it, or `PLAUSIBLE` with the live scenario and break that would settle it.

Done when every finding is listed with its verifier's verdict and evidence. A finding with no verdict is neither fixed nor reported, and the readout's counts come only from these verdicts.

## 4. Fix and decide

Decide in the main session. Rank confirmed findings by what the guarded check protects, highest risk first, using the coverage map's risk or launch rows when the harness has one.

Fix now:

- A check with no failing-case test: add the test that feeds the broken case.
- A check that passes on empty, on an exception, or on the code's own output, when the design says unambiguously what it should check: tighten it.
- A command, flag, scenario name, probe subcommand, or path in a doc or skill that no longer exists: correct it.
- A coverage rating stronger than its evidence: lower it and name the planned break that would earn it back.
- A check that misled before the fix: record it where the harness tracks known gaps, if it has such a place.

Prove each new or changed test red-green: it fails against the broken copy and passes against the real code. A fix to a check needs a test too, one that fails when the fix is reverted. Then hand every new or changed test to a fresh verifier with the same break, so the audit cannot add a useless test of its own.

Leave for the developer, with a recommendation each: deleting a test or check, changing an expected value, a new check or probe command, a change to what a read returns when it succeeds, anything `PLAUSIBLE`, and any fix in another repo.

Never loosen an assertion or change an expectation to turn a run green; a bug stays failing with the correct expectation and goes to the ticket tracker.

Rerun the unit suite and `weakened.py --since HEAD` on your own changes; any lead it prints must be one you justify in the readout. Leave the fixes uncommitted and offer the commit in the readout, titled `Audit harness checks: <one-line summary>`: the next audit finds its starting point from that title.

Done when the suite is green, every fix has a red-green proof and a verifier's `CONFIRMED`, and the fixes are left uncommitted with the commit offered.

## Readout

The reader acts on this alone: keep it short, in plain words, without rubric IDs. Every item says what was wrong, what breakage it would have hidden, and what was done or needs doing.

```
Audit harness checks, <date>: <one line: can we trust the suite, and the biggest risk>
Since <short sha of weakened.py's starting commit> · <n> checks broken, <n> caught · <n> findings, <n> confirmed, <n> refuted

Needs you
1. <action>: <what breakage this hides, in user terms>. Recommend: <choice and why>.

Fixed (uncommitted)
- <check or test> could pass when <broken behavior>; <what changed>. Guards <feature or risk>.

Updated
- <file>: <what changed and why, one line>

Run live to settle
- <scenario> with <break>: would show whether <claim>.
```

Omit an empty section. "Needs you" holds at most five items, ordered by risk; list the rest in the proposed commit body and end the section with `<n> lower-risk items in the commit body`. When there are fixes, the last item offers the commit: `Commit these fixes as "Audit harness checks: <summary>"? Recommend yes; the next audit starts from it.` Refuted findings appear only in the count.

## Reply

The readout above, and nothing else.
