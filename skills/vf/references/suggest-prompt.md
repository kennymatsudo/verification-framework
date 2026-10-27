# Suggestion prompt

Spawn one read-only subagent on a mid-tier model with this prompt. Fill in the repo path and the harness path.

---

The repo at `<repo path>` has a verification harness at `<harness path>`: its `rules.md`, `harness.json`, feature map in `features/`, and tools. Find the gaps that would most help an agent prove its changes. Do not run anything except `git log`, and do not edit files.

Collect candidates from each source, and cite where each came from:

1. **Unchecked behaviors.** Every behavior in the feature map with no `check` and no `unreachable` block.
2. **Unmapped features.** User-facing routes, commands, or screens in the code with no feature file. Cite the source path that defines each.
3. **Churn without proof.** Run `git log --since=60.days --name-only --format=` and find source files that changed often. Name the features they belong to that have no check.
4. **Hand-written reads.** Raw SQL, curl commands, or ad-hoc scripts in docs, runbooks, scripts, or agent instruction files that read app state. Each one is a probe waiting to be written.
5. **Known bugs.** If the prompt lists recent bug reports, the features they touched.

For each candidate, return: what to add in plain words (for example "a way to read an order's payment state"), the kind of component (feature file, probe, action, or check), the source citation, and one sentence on why it matters. Rank by how often an agent changing this code would need it. Return at most ten.
