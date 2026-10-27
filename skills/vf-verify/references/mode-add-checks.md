# Add feature checks

Follow this when vf-verify runs in add-checks mode. The Guardrails in vf-verify's `SKILL.md` apply throughout.

You own checks that prove the agreed behavior on the real app and catch a deliberate break. Run when the user asks to build proof or the verify mode delegates missing proof within its agreed scope. Preserve an existing-checks-only restriction. Product implementation is a separate job.

## 1. Read the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.

Run `<harness>/scripts/framework/vf.py validate --written-for 4` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop. Then read its `settings.md` and `rules.md`, the feature map in `features/`, the results in `status.md`, the caveats in `notes.md`, and the tool guide in `tools.md`.

Done when the target, harness, setup gate, existing coverage, and tools are known, or a named blocker stops the work.

## 2. Agree on what to build

- **Named outcome or verification handoff:** translate the supplied scope and acceptance sources into components, such as a checkout feature file and a check for checkout.pay, plus any probe or action the check needs that `tools.md` doesn't list. The requested outcome authorizes building those components.
- **Suggestions requested or no outcome named:** spawn a read-only subagent on a mid-tier model with `references/suggest-prompt.md`. List the session's tools and match a ticket tracker by what it can search; supply recent relevant bug reports when available, or name that source as unsearched. Show three to five numbered suggestions, one line each with its reason, and recommend one. Build nothing until the user picks.

Follow `references/verification-plan.md` before building.

Done when the preview and component list are shown, acceptance decisions are resolved, the plan is saved, and suggestions have a user choice.

## 3. Build the components

Follow `references/mode-add-tools.md` for each probe or action the plan needs, before building the checks that use it. Pass the harness, what each check needs the tool to read or do, and the permissions the plan agreed. A tool whose proof is blocked blocks the checks that use it; report them Not verified with that blocker. Follow `references/harness-components.md` for each other selected kind. Before building, find what the project already has for the feature's entry point: ways to drive it (end-to-end specs, API clients, CLI commands, fixture scripts), places to read results back, and the modules that own database and external API connections. Reuse them through the harness's recipes where they already suffice. Update settings when a component fills a `none yet` line.

Add or update every served sub-feature's behavior, entry point, and proof line. Keep requirements in their original source, linked from the feature file's Verification plan. Publish each new command in `tools.md`.

Done when every selected component exists, each served ID names its proof or explicit gap, and every available command has a guide entry and --help without service access.

## 4. Prove the components

`vf.py run` runs the doctor before each check and stops when the app is not ready; start the app only as settings permit, and stop on a wrong or unknown running version. Before a new or materially changed check's first proof run, get the blind review `references/verification-plan.md` requires.

Run each component's proof from `references/harness-components.md` against the real app and show the output. Run each check through `scripts/framework/vf.py run --` and the exact command its feature file records, from the directory its tool guide names, so the recorded recipe is the one proven. A pass on a scratch fix proves only that fix, not the user's checkout.

Every accepted run has already refreshed `status.md`; for a behavior whose proof is blocked, record why with `vf.py not-verified`, as the harness's Reporting section describes, then run `vf.py validate --require-evidence --run-help`. Clean up only what this run created, stopping instances it started with the Stop command; name anything still open.

Done when every component has proof or a named blocker, every served ID's status line is Verified or says why not, the map check passes or its blocker is named, and cleanup leaves evidence inspectable.

## Guardrails for this mode

- Add levels of proof, extra skills, or workflow rules only when the user asks for them.
- Edit existing files outside the harness only when the user named them for this workflow or authorized the exact edit. Do not change Git ignore files or decide evidence retention.

Reply: in the shape `references/messages.md` gives. First, how many of the agreed behaviors are now Verified. Then one line per behavior in the preview's words, with its verdict: for Verified, what you broke to prove the check fails; otherwise, why not and what would close it. Then one line for each expectation you changed in a check after the plan was agreed, and one for test data left anywhere shared, such as a sandbox; local test data needs no line. Add nothing else: commands, code names, IDs, versions, workarounds, and cleanup belong in the feature file, `notes.md`, and `tools.md`.
