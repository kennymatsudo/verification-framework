---
name: add-feature-checks
description: >-
  Add checks for a feature to an existing verification harness, putting the feature
  on the harness's feature list, and prove each check can fail. Use for "add checks
  for checkout", "add a check for this behavior", "set up exploration", or "what
  should we add next?". Use add-tools to add a probe or action on its own,
  setup-verification to establish readiness, and verify-change to complete
  verification of a change.
---

# Add feature checks

You own checks that prove the agreed behavior on the real app and catch a deliberate break. Run when the user asks to build proof or verify-change delegates missing proof within its agreed scope. Preserve an existing-checks-only restriction. Product implementation is a separate job.

## 1. Read the harness

Use the app harness the user supplied, or glob `verify-*/rules.md` in the skills directories of the current folder and each folder above it up to the repo's top level, nearest first (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`). Ask which when several match. If none matches the named app, stop and name setup-verification.

Read its `settings.md` and `rules.md`, then run `<harness>/scripts/framework/validate.py`. If it stops on incomplete setup, report its blocker and next action, name setup-verification to resume, and stop. Then read the feature map in `features/`, the results in `status.md`, and the tool guide in `tools.md`.

Done when the target, harness, setup gate, existing coverage, and tools are known, or a named blocker stops the work.

## 2. Agree on what to build

- **Named outcome or verification handoff:** translate the supplied scope and acceptance sources into components, such as a checkout feature file and a check for checkout.pay, plus any probe or action the check needs that `tools.md` doesn't list. The requested outcome authorizes building those components.
- **Exploration setup:** build the components under "Exploration setup" in `references/harness-components.md`.
- **Suggestions requested or no outcome named:** spawn a read-only subagent on a mid-tier model with `references/suggest-prompt.md`. List the session's tools and match a ticket tracker by what it can search; supply recent relevant bug reports when available, or name that source as unsearched. Show three to five numbered suggestions, one line each with its reason, and recommend one. Build nothing until the user picks.

Follow the harness's Verification plan rules before building.

Done when the preview and component list are shown, acceptance decisions are resolved, the plan is saved, and suggestions have a user choice.

## 3. Build the components

Load add-tools by name for each probe or action the plan needs, before building the checks that use it. Pass the harness, what each check needs the tool to read or do, and the permissions the plan agreed. A tool whose proof is blocked blocks the checks that use it; report them Not verified with that blocker. Follow `references/harness-components.md` for each other selected kind. Before building, find what the project already has for the feature's entry point: ways to drive it (end-to-end specs, API clients, CLI commands, fixture scripts), places to read results back, and the modules that own database and external API connections. Reuse them through the harness's recipes where they already suffice. Update settings when a component fills a `none yet` line.

Add or update every served sub-feature's behavior, entry point, and proof line. When there is a requirements source, maintain its clause links in `features/requirements.md`; keep requirements in their original source. Publish each new command in `tools.md`.

Done when every selected component exists, each served ID names its proof or explicit gap, and every available command has a guide entry and --help without service access.

## 4. Prove the components

Run the doctor, starting the app only as settings permit; stop on a wrong or unknown running version. Before a new or materially changed check's first proof run, get the blind review the harness's Verification plan requires.

Run each component's proof from `references/harness-components.md` against the real app and show the output. Run each check through the exact command its feature file records, from the directory its tool guide names, so the recorded recipe is the one proven. A pass on a scratch fix proves only that fix, not the user's checkout.

Record results in `status.md` as the harness's Reporting section describes, including its `validate.py --run-help` run. Clean up only what this run created, stopping instances it started with the Stop command; name anything still open.

Done when every component has proof or a named blocker, every check line records its break-test status, the map check passes or its blocker is named, and cleanup leaves evidence inspectable.

## Guardrails

- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.
- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.
- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.
- Never forge an event the real system would produce, and never loosen a check to turn a run green.
- Add levels of proof, extra skills, or workflow rules only when the user asks for them.
- Edit existing files outside the harness only when the user named them for this workflow or authorized the exact edit. Do not change Git ignore files or decide evidence retention.

Reply: in the harness's Messages shape. First, how many of the agreed behaviors are now Verified. Then one line per behavior in the preview's words, with its verdict: for Verified, what you broke to prove the check fails; otherwise, why not and what would close it. Then one line for each expectation you changed in a check after the plan was agreed, and one for test data left anywhere shared, such as a sandbox; local test data needs no line. Add nothing else: commands, code names, IDs, versions, workarounds, and cleanup belong in the feature file, `status.md`, and `tools.md`.
