# Verifier prompt

Fill in the bracketed parts.

> Each item below claims a check or test in this project's harness passes when the behavior it guards is broken. Prove or refute each one. Do not edit the project tree, run live scenarios, or call any external service.
>
> Work in a scratch copy: `D=$(mktemp -d)`, copy [the paths the unit suite needs] into it, skipping gitignored files, then run `[suite command]` from `$D`, or call the check directly with inputs you build in the shape the harness's read layer returns.
>
> For each item, apply the break the failure scenario describes and return one verdict:
> - **CONFIRMED**: the exact break, the command, and the output showing the check or test stayed green.
> - **REFUTED**: the `file:line` and quoted code that makes it go red.
> - **PLAUSIBLE**: only a live run could tell. Name the scenario and the break to apply.
>
> [For a new or changed test: also show it fails with the break and passes without it.]
>
> Items:
> [findings]
