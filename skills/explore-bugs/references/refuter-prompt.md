# Refuter prompt

Give the subagent only this prompt, filled in. Do not include your own reasoning about why the break is real.

---

A test round claims this behavior is broken in the app at `<repo path>`:

`<the claimed break, one sentence>`

Recipe: `<command>`. Runs: `<k of n>`. Evidence: `<evidence paths>`. Known issues searched: `<where, and what matched>`.

Your job is to show the claim is wrong. Do not edit files or run anything with a side effect outside this machine. Try each:

1. **The harness.** Read the code that drove the run and the code that judged it. Did it send something a real user or system never sends, read the wrong record, or judge too early?
2. **The environment.** Do the logs or evidence show a dropped connection, stale code, a quota, or another run's data?
3. **A known issue.** Is this the same behavior as an issue already open? Same behavior means same trigger and same symptom, not the same area.
4. **The expectation.** Does the code or a design document say this behavior is intended?

Return one verdict: `refuted: harness`, `refuted: environment`, `refuted: known <issue>`, `refuted: intended`, or `stands`. Cite `path:line` or the evidence line for each point you checked, and say which you could not check.
