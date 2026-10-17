# Check reader

Fill in the bracketed parts and give this to a mid-tier subagent, one per check script:

> Read the check script `[path]` and the feature files that name it: `[feature file paths]`. Each feature file's "How a user reaches it" section lists the app's real entry points. Don't run anything.
>
> For each behavior ID `[IDs]` the script checks, answer two questions:
>
> 1. **Does it act the way a user does?** Quote the `file:line` where the script takes the action. Answer yes if the action goes through an entry point in "How a user reaches it". Answer no if it calls app functions or imports app modules to act, uses a test-only route, or writes state directly. Otherwise answer unclear.
> 2. **Does it look at the result itself?** Quote the `file:line` of the read that decides pass or fail. Answer yes if it reads the stored row, sent message, written file, or rendered screen directly. Answer no if the verdict rests only on the app's reply, or the read goes through the app's own models or logic. Otherwise answer unclear.
>
> Return one line per behavior and question: `<ID> | <1 or 2> | <yes, no, or unclear> | <file:line> | <the quoted code> | <one clause why>`. Quote code exactly. Use unclear rather than guess.
