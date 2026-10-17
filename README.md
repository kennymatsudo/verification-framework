# verification-framework

Agent skills for proving a change works on the running app, not just in tests. They use the [Agent Skills](https://agentskills.io) format and work with Claude Code, Codex, Cursor, and any other agent the `skills` CLI supports.

The skills build and run a verification harness in each app's repo. A harness is one folder with the app's settings, feature map, results, tool guide, tools, and evidence, in the same layout for every app. It keeps requirements, feature claims, and current results apart, and ties every result to the code versions and behavior actually tested, across every repo the app runs from.

See [USAGE.md](USAGE.md) to set up a harness, verify changes, and keep the harness honest. See [docs/internals.md](docs/internals.md) for the file formats and scripts underneath.

## Skills

Start with verification-framework if you don't know which skill you need.

| Skill | What it does |
| --- | --- |
| [verification-framework](skills/verification-framework/SKILL.md) | Takes any request, looks at what the repo already has, and runs the matching skills in order. |
| [setup-verification](skills/setup-verification/SKILL.md) | Creates or resumes a harness and proves the app's environment is ready. Feature coverage can start empty. |
| [add-feature-checks](skills/add-feature-checks/SKILL.md) | Agrees on expected behavior, builds feature tools and checks, and proves those checks catch a deliberate break. |
| [verify-change](skills/verify-change/SKILL.md) | Previews the behaviors and evidence limits, checks setup, delegates missing proof, runs checks on the requested version, and records results. The generated app skill delegates here. |
| [audit-coverage](skills/audit-coverage/SKILL.md) | Finds requirements and features with no check, and checks that no longer match the code or the running app, and fixes the harness's own files. |
| [explore-bugs](skills/explore-bugs/SKILL.md) | Runs one round of exploratory testing to find bugs nobody wrote down, confirms each break, turns it into a failing check, and records the round in a ledger. |
| [verify-pr](skills/verify-pr/SKILL.md) | Verifies a teammate's PR with the end-to-end harness: decides which of its claims belong there, builds those checks, runs them on the PR's build, sorts the failures, and drafts a PR comment. |
| [audit-weak-checks](skills/audit-weak-checks/SKILL.md) | Sweeps the harness for checks and tests that would still pass if what they guard broke, verifies each finding independently, and fixes the clear-cut ones on a branch. |
| [explain-harness](skills/explain-harness/SKILL.md) | Explains to a teammate who didn't build the harness what it checks and how far to trust each pass, one level of detail at a time. Read-only. |

## Requirements

| Need | Required | Used for |
| --- | --- | --- |
| Git | Yes | Code versions in evidence, and scratch worktrees for planned breaks |
| Python 3 | Yes | The harness's `check.py`, `code_state.py`, `replay.py`, and `clip.py`, which use only the standard library |
| ffmpeg | Optional | Still frames for agents and video clips for PRs, from recorded runs. Without it, agents diagnose from the failure's snapshot and logs |
| Chrome, Chromium, or Edge | Optional | Captions on clips. An ffmpeg with the subtitles filter also works. Without either, cut clips with `--no-captions` |

Install the optional tools with `brew install ffmpeg` and `brew install --cask google-chrome` on macOS, the package manager's `ffmpeg` and `chromium` on Linux, or `winget install Gyan.FFmpeg` and `winget install Google.Chrome` on Windows. In a harness, `scripts/clip.py --check` reports what the current machine can make and prints the install line for anything missing. Agents never install these on their own.

This table covers only what the framework needs. What the app needs to run, such as its database or a login, is recorded in its harness during setup.

## Install

With the [`skills` CLI](https://skills.sh), for any supported agent:

```sh
npx skills add kennymatsudo/verification-framework          # pick skills and agents interactively
npx skills add kennymatsudo/verification-framework --list   # list skills without installing
npx skills add kennymatsudo/verification-framework -s <skill-name> -g   # one skill, user-level
```

The `skills` CLI needs Node.js. The Claude Code plugin below does not.

As a Claude Code plugin:

```
/plugin marketplace add kennymatsudo/verification-framework
/plugin install verification-framework@verification-framework
```

The plugin lists each skill with a `verification-framework:` prefix, so the starting skill is `/verification-framework:verification-framework`.

When you install skills one at a time, install verify-change and add-feature-checks along with setup-verification, because the skill setup generates depends on both. verification-framework runs only installed skills. If its plan needs one that is missing, it stops and prints the install line.

To check the install, run `/verification-framework` and ask "what can this framework do?". It lists its playbooks, one line each, and asks which to run.

## Understand what setup adds to an app repo

Setup creates a thin `verify-<app>` skill in the app's repo, such as `verify-storefront`. It names the app and its harness, then hands the work to verify-change. The harness's settings hold the app's commands.

Run add-feature-checks to add checks directly. verify-change also calls it for missing proof within the requested scope. Evidence stays inside the harness, and the team decides what to track in Git.
