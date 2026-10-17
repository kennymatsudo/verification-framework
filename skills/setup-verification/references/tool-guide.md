# Tool guide template

Write `tools.md` in the harness using the format below, with one entry per available command. Include the doctor during setup; add-feature-checks adds feature tools. Link existing project command documentation where useful. Do not list planned tools as available.

```markdown
# <App> developer tools

Use these commands for debugging, investigation, or verification. A read reports current state; it does not by itself prove a feature works.

## <Question or task the tool addresses>

Use when: <situation where this command helps, and when to use another tool>.

Run from <working directory relative to the project root>:

`<command with an example input>`

- Inputs: <required identifiers and how to obtain them>.
- Environment: <configuration, code checkouts, services, and access required; how to identify the target environment>.
- Permissions: <read-only, or side effects and the approval/ownership rules the command enforces>.
- Result: <output fields and what success establishes>.
- Failure: <exit codes, missing-record versus unavailable-service meanings, and next action>.
- Limits: <what this observation or action does not prove>.

Help: `<command> --help`.
```

After permission to edit the applicable project agent instructions, add a short pointer using its existing format:

```markdown
For <app> readiness and state inspection, use the commands in [developer tools](<guide path relative to this instruction file>). Read the entry's prerequisites, permissions, and limits before running it. These commands also support debugging outside verification.
```

Verify the pointer resolves from the instruction file. A fresh agent given only the project instructions and a debugging request should be able to find the guide and invoke the relevant tool without loading a verification skill.
