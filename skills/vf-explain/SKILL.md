---
name: vf-explain
description: >-
  Explain to a teammate who didn't build an app's verification harness what it
  checks and how far to trust each pass: one real check walked through five
  plain questions, a tally of where trust is weakest, and suggested follow-ups,
  one level of detail at a time. Read-only; never runs the app. Use for "can I
  trust these checks?", "why should I believe this Verified?", "what does
  verify-shop actually check?", "how is checkout checked?", "show me what we
  have". Use vf to audit the harness for checks that can't fail or
  behaviors with no check, and vf-verify to run checks.
---

# Explain the harness

You own an honest, short answer to "how far can I trust this?" for someone who didn't build the harness and didn't watch it run. You explain what the harness records. Answer only what was asked, and offer the next level instead of giving it.

## 1. Find the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up. Say also that with no harness there is nothing to explain yet, and, with several, ask which with the session's structured question tool if it has one, else a `Needs you:` line.

Run `<harness>/scripts/framework/vf.py validate --written-for 3` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. An incomplete setup means no pass can be trusted yet, so say so. Keep its errors and warnings: a format error or "last pass is N commits behind HEAD" is a trust fact.

Done when one harness is chosen and its `vf.py validate` output is in hand, or you stopped with the reason.

## 2. Gather the facts

Run `python3 <harness>/scripts/framework/trust_facts.py <harness>`. Its `--help` describes every field. When the file is missing, the harness predates the installed framework: name vf to update it and stop. It reads only what the harness records, so it settles questions 3 to 5 below; questions 1 and 2 need the check's code.

Done when you have its JSON.

## 3. Pick the scope

Match the request to one scope:

- **No specific question, or "can I trust these checks?"**: the opener in step 5.
- **A feature, behavior, or check named**: those behaviors.
- **A pass in a report or pull request**: the behaviors that result covers.
- **One question across the harness**, such as "which checks take the app's word?": that question for every check.
- **"Show me" or "something to share"**: run the script with `--html <path>` outside the repo's tracked files, give the path, and say the page shows what the harness records but not questions 1 and 2. When `<harness>/recordings.html` exists, also give its path as where to see each check's latest run and watch recordings.

Done when the scope names its behaviors by ID.

## 4. Answer the five questions

For each check in scope, answer each question yes, no, or not recorded, with its source:

1. **Does it do what a user does?** Open the check's command and quote the `file:line` where it acts. Yes when it goes through an entry point listed in the feature's "How a user reaches it"; no when it calls app functions directly, uses a test-only route, or writes state itself.
2. **Does it look at the result itself?** Quote the `file:line` of the read that decides the pass. Yes when it reads the stored row, sent message, written file, or rendered screen directly; no when the verdict rests on the app's own reply or reads through the app's code. Say whether it reads what the user sees or only stored state, from the proof line's `reads`.
3. **Have we seen it catch a problem?** Yes only when `break.on_hand` and `break.failed_steps` is not empty: say what was broken and which step failed. A break `aimed_at` other behaviors is no for this one, even if its steps failed. A break whose record isn't in this checkout is "recorded, but the proof isn't here". No break is no.
4. **Did it run on the code you care about?** From `result.code`: the commit, how far behind HEAD, and uncommitted changes. Add `vf.py validate`'s warnings for that behavior.
5. **Can you see the proof?** The saved run for the pass and for the break, and the check's command to rerun it.

Add the behavior's `caveats` as what a pass doesn't show. For every no, say in user terms what bug could still pass, such as "a bug that skips sending the email but reports success would still pass".

For questions 1 and 2 across more than three check scripts, spawn one mid-tier subagent per script with `references/check-reader.md`, and check each quoted line yourself before using it.

Done when every check in scope has all five answers, each with a quoted line, a field, or "not recorded".

## 5. Reply

Write for someone who has never heard the framework's terms. Say "broke it on purpose and the check failed" instead of break-tested or planned break, "saved run" instead of evidence file, and "your checks" instead of harness. Leave out probe, doctor, recipe, and sub-feature; give a behavior's ID only in parentheses after its plain name.

Use this shape and add nothing outside it, one sentence per line, leaving out lines with nothing to say:

```
<Yes, Mostly, or Not yet>: <the one reason that decides it>.

How we know <behavior in plain words> works (<ID>):
- Acts like a user: <yes or no>. <what it does>, `<file:line>`.
- Looks for itself: <yes or no>. <what it reads, seen or stored>, `<file:line>`.
- Seen catching a problem: <yes or no>. We <what was broken> and it failed at "<step>".
- Ran on your code: <commit>, <on HEAD or N commits behind>, <uncommitted files by name, and whether any is app code>.
- Proof: <saved run path>; rerun with `<command>`.
Doesn't show: <the caveats>.

<Tally in two lines at most, weakest first: never seen failing, ran on older code, no check.>
<Only when one exists: weak checks go to vf's audit mode, missing checks to vf-verify's add-checks mode.>

Ask about: <follow-up> · <follow-up> · <follow-up>
```

- **Opener:** pick the check with the most yes answers, so the questions are taught by example, and show any no honestly. Build the tally from the script's `tally` and `vf.py validate`'s warnings, plus the one item under `known_failing` or `may_mislead` that matters most; the rest become a follow-up.
- **A named behavior or pass:** the block for each check in scope, then the tally only if it changes the answer. Past three checks, give one line per check with its weakest answer and offer the details.
- **Follow-ups:** two or three, drawn from this harness, weakest spot first, naming real behaviors: "the 3 checks never seen failing", "how order.receipt checks the email". Offer them with the structured question tool if the session has one; otherwise the `Ask about:` line is the last line.

Done when the reply follows the shape, answers only the asked scope, every claim traces to a field or a quoted line, and nothing follows the follow-ups.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Read only. Don't start the app, run a check, or edit the harness; send a fix to the skill that owns it.
- Never call a check trustworthy past what its fields and code show. "Not recorded" is an answer.

Reply: the answer for the asked scope in the shape from step 5, ending on two or three follow-ups.
