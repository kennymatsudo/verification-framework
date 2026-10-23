#!/usr/bin/env python3
"""Find the framework's skills and the repo's verification harnesses, as JSON.

Usage: locate.py [--repo DIR]

Prints one JSON object:

- skills: each framework skill's name mapped to the path of its SKILL.md, or
  null when it isn't installed anywhere this script looks.
- missing: the names whose SKILL.md wasn't found.
- harnesses: each harness folder found by verify-*/rules.md in the skills
  directories of DIR and of each folder above it up to its Git top level,
  nearest first, so an app that is one folder of a monorepo finds its own.

A skill is looked for beside the skill folder holding this script first (the
installed vf, or a harness running its scripts/framework/ copy), where the
Claude Code plugin, the skills CLI, and vf.py sync all put it, then in those
same project skills directories, then in the same directories under the home
directory. DIR defaults to the current directory.

Exits 0 when every skill is found, 1 when any is missing (the JSON still
prints), and 2 when DIR is not a directory, with the reason on a STOPPED: line
on stderr.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILLS = (
    "vf-verify",
    "vf-explain",
)
SKILLS_DIRS = (".claude/skills", ".agents/skills", ".pi/skills", ".cursor/skills")


def repo_root(start):
    """The Git top level that holds start, or start itself outside a repo."""
    found = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=start, capture_output=True, text=True
    )
    return Path(found.stdout.strip()) if found.returncode == 0 else start


def project_folders(start):
    """start and each folder above it up to its Git top level, nearest first; just start outside Git."""
    start = start.resolve()
    top = repo_root(start).resolve()
    if top != start and top not in start.parents:
        return [start]
    folders = [start]
    while folders[-1] != top:
        folders.append(folders[-1].parent)
    return folders


def skill_folder(script):
    """The skill folder holding script: the nearest folder above it with a SKILL.md, so a harness's
    scripts/framework/ copy resolves to the harness and the installed copy to vf."""
    script = script.absolute()
    return next((folder for folder in script.parents if (folder / "SKILL.md").is_file()), script.parent.parent)


def locate(router_dir, start, home):
    """Where each framework skill is installed and which harnesses the project holds, as the JSON this script prints."""
    # The plugin and the skills CLI may reach this skill through a symlink, so
    # its siblings can sit beside the link or beside the real folder.
    folders = project_folders(start)
    search = [router_dir.parent, router_dir.resolve().parent]
    search += [folder / d for folder in folders for d in SKILLS_DIRS] + [home / d for d in SKILLS_DIRS]

    skills = {}
    for name in SKILLS:
        paths = (base / name / "SKILL.md" for base in search)
        skills[name] = next((str(p) for p in paths if p.is_file()), None)

    harnesses, seen = [], set()
    for skills_dir in (folder / d for folder in folders for d in SKILLS_DIRS):
        for rules in sorted(skills_dir.glob("verify-*/rules.md")):
            real = rules.parent.resolve()
            if real not in seen:
                seen.add(real)
                harnesses.append(str(rules.parent))

    return {
        "skills": skills,
        "missing": [name for name, path in skills.items() if path is None],
        "harnesses": harnesses,
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n", 1)[0],
        epilog=__doc__.split("\n\n", 2)[2],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", type=Path, help="the folder to search from (default: the current directory)")
    args = parser.parse_args()

    repo = args.repo or Path.cwd()
    if not repo.is_dir():
        print(f"STOPPED: {repo} is not a directory", file=sys.stderr)
        return 2

    found = locate(skill_folder(Path(__file__)), repo.absolute(), Path.home())
    print(json.dumps(found, indent=2))
    return 1 if found["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
