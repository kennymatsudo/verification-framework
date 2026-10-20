# verification-framework

Agent skills that prove a code change works on your real, running app, not just in unit tests. They use the [Agent Skills](https://agentskills.io) format and work with Claude Code, Codex, Cursor, and any other agent the `skills` CLI supports.

Use them when passing unit tests is not enough: the change crosses a database, another service, a browser, or anything else a unit test replaces with a stand-in.

## How it works

The skills build and run a verification harness in your app's repo. A harness is one folder holding how to start the app, which behaviors to check, the programs that check them, a guide to those tools, and a record of every run. Requirements, what each feature should do, and the latest results live in separate files. Every harness has the same layout, so anyone who knows one can read another.

Every result names the behavior and the code version it tested, in every repo the app runs from. A behavior is reported Verified only when its check ran on the real app and had already been shown to fail when the behavior was broken on purpose. Anything without that proof is Not verified, never a pass.

[USAGE.md](USAGE.md) walks through setting up a harness, adding checks, verifying a change, and keeping the harness honest. [docs/internals.md](docs/internals.md) describes the files and scripts underneath.

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

If you install skills one at a time, install verify-change, add-feature-checks, and add-tools along with setup-verification. The skill that setup generates depends on all three. verification-framework runs only installed skills, and when its plan needs one that is missing, it stops and prints the install line.

To check the install, run `/verification-framework` and ask "what can this framework do?". It lists its playbooks, one line each, and asks which to run.

## Try it

In your app's repo:

```text
/setup-verification Set up verification for this app.
```

Setup reads how your app starts, asks only what it could not find, and proves the app can be started and inspected. It leaves a small `verify-<app>` skill in the repo, such as `verify-storefront`, that names the app and its harness and hands the work to verify-change. The app's commands live in the harness's settings, not in the skill.

From there, run add-feature-checks to add checks for a feature, and the `verify-<app>` skill to verify a change. verify-change also builds missing checks within the requested scope. Evidence stays inside the harness, and your team decides what to track in Git.

## Skills

If you don't know which skill you need, start with verification-framework.

| Skill | What it does |
| --- | --- |
| [verification-framework](skills/verification-framework/SKILL.md) | Takes any request, looks at what the repo has, and runs the matching skills in order |
| [setup-verification](skills/setup-verification/SKILL.md) | Creates or resumes a harness and proves the app's environment is ready |
| [add-feature-checks](skills/add-feature-checks/SKILL.md) | Agrees on expected behavior, builds checks, and proves each catches a deliberate break |
| [add-tools](skills/add-tools/SKILL.md) | Adds a probe or action apart from any check and proves it on the real app |
| [verify-change](skills/verify-change/SKILL.md) | Previews, runs the checks a change touches on the requested version, and records results |
| [audit-coverage](skills/audit-coverage/SKILL.md) | Finds requirements and features with no check, and checks that no longer match the app |
| [audit-weak-checks](skills/audit-weak-checks/SKILL.md) | Finds checks and tests that would still pass if what they guard broke, and fixes the clear ones |
| [explore-bugs](skills/explore-bugs/SKILL.md) | Runs one round of exploratory testing and turns each confirmed bug into a failing check |
| [verify-pr](skills/verify-pr/SKILL.md) | Tests a teammate's PR, or several across repos together, on the real app, sorts the failures, and drafts a comment with a demo video |
| [explain-harness](skills/explain-harness/SKILL.md) | Tells a teammate what the harness checks and how far to trust each pass. Read-only |

[Choose a skill](USAGE.md#choose-a-skill) in USAGE.md has example requests for each.

## Requirements

| Need | Required | Used for |
| --- | --- | --- |
| Git | Yes | Code versions in evidence, scratch worktrees for planned breaks |
| Python 3 | Yes | The five framework scripts, standard library only |
| ffmpeg | Optional | Still frames for agents and video clips for PRs, from recorded runs |
| Chrome, Chromium, or Edge | Optional | Captions on clips |

The five scripts are `validate.py`, `code_state.py`, `break_session.py`, `replay.py`, and `clip.py`. Without ffmpeg, agents diagnose from the failure's snapshot and logs. Without a browser, an ffmpeg with the subtitles filter also draws captions, and with neither you can cut clips with `--no-captions`.

Install the optional tools with `brew install ffmpeg` and `brew install --cask google-chrome` on macOS, the package manager's `ffmpeg` and `chromium` on Linux, or `winget install Gyan.FFmpeg` and `winget install Google.Chrome` on Windows. In a harness, `scripts/framework/clip.py --check` reports what this machine can make and prints the install line for anything missing. Agents never install these on their own.

What the app itself needs to run, such as its database or a login, is recorded in its harness during setup.

## License

MIT. See [LICENSE](LICENSE).
