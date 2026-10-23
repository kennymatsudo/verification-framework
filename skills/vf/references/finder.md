# Finder prompt

Fill in the bracketed parts.

> You are auditing one slice of a test harness for checks that would pass even if what they guard were broken. Read-only: do not edit files, run live scenarios, or call any external service. You may run the unit suite (`[suite command]`) and the harness's `--help` commands from the project root.
>
> Slice: [files]. Lines from the automated sweep that fall in this slice: [break_checks SURVIVED lines, smells lines, weakened lines].
>
> Read every check and test in the slice against the rubric below. For each automated line, return a finding or one sentence saying why it is fine (for example, a removed assertion that moved to a stricter one; quote both).
>
> Return each finding as:
> - `file:line` and the quoted code (at most 10 lines)
> - rubric ID
> - Failure scenario: `This passes even when <broken behavior> because <reason>.`
> - Proposed fix, in one sentence
>
> Return no finding without a concrete failure scenario. Style, naming, and speed are out of scope.
>
> [rubric.md contents]
