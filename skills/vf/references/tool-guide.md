# Tool entries

Record each available command as an entry under `tools` in `harness.json`, then run `scripts/framework/vf.py tools` to write `tools.md`, the guide people and agents read. Never edit `tools.md` by hand: `validate.py` fails one that differs from what `vf.py tools` writes. Include the doctor during setup; vf-verify adds every later tool. Do not list planned tools as available.

```json
"tools": {
  "<short name, such as doctor or probe>": {
    "command": "<command with an example input>",
    "use_when": "<situation where this command helps, and when to use another tool>",
    "run_from": "<a folder relative to the project root; leave out for the root>",
    "inputs": "<required identifiers and how to obtain them>",
    "environment": "<configuration, code checkouts, services, and access required; how to identify the target environment>",
    "permissions": "<read-only, or side effects and the approval/ownership rules the command enforces>",
    "result": "<output fields and what success establishes>",
    "failure": "<exit codes, missing-record versus unavailable-service meanings, and next action>",
    "limits": "<what this observation or action does not prove>"
  }
}
```

`command`, `use_when`, `permissions`, and `limits` are required; the rest are optional. `<command> --help` must work without connecting to anything, and `validate.py --run-help` runs it.

Link the guide from the project instructions the agent actually loads, scoped to the app in a monorepo. Ask before editing an existing instruction file unless the user authorized that exact edit; without permission, keep the guide, show the proposed pointer, and report discovery as not wired. With permission, add a short pointer using the file's existing format:

```markdown
For <app> readiness and state inspection, use the commands in [developer tools](<path to tools.md relative to this instruction file>). Read the entry's prerequisites, permissions, and limits before running it. These commands also support debugging outside verification.
```

Verify the pointer resolves from the instruction file.
