# Reader prompt

Spawn one read-only subagent per feature file on a mid-tier model with this prompt. Fill in the paths.

---

Compare the feature file at `<feature file>` with the source code in `<repo path>`. Do not run the app, its tests, or a build. Do not edit files. You may run `git log` and `git blame`.

1. Find the entry point for each "How a user reaches it" line, and cite `path:line`. Name any entry point in the code that the file does not list.
2. For each sub-feature, read the code that implements it and say whether the file's description still matches. Cite the code for every mismatch.
3. For each proof command, check that the command and what it reads still exist, and that the code it covers has not changed shape (renamed fields, moved routes, new required inputs).
4. Name any user-facing behavior in this feature's code that has no sub-feature.

Return:

- **Summary:** the feature in two sentences, from the code.
- **Entry points:** each one, with `path:line`.
- **Drift:** each mismatch, with the file's claim, what the code does, and `path:line`. Write "none" if there is none.
- **Missing:** behaviors and entry points with no line in the file, each with `path:line`.
- **Live recipe:** the shortest way to see each sub-feature work on the running app, using the harness's tools where they fit.
