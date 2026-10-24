"""Load practice repos and eval cases from disk."""

import fnmatch
import json
import re

from . import CASES, PRACTICE

PREPARE_LEVELS = ("bare", "ready", "verified")


class CaseError(Exception):
    pass


def frontmatter(text):
    """(settings, body) for a Markdown file with a YAML-ish block on top: `key: value` and `key: [a, b]` lines only."""
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    settings = {}
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise CaseError(f"frontmatter line is not 'key: value': {line}")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            settings[key.strip()] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
        elif re.fullmatch(r"-?\d+", value):
            settings[key.strip()] = int(value)
        else:
            settings[key.strip()] = value.strip("'\"")
    return settings, body.lstrip("\n")


def load_practice(name):
    """A practice repo's practice.json with its folder added as 'dir' and its base chain resolved."""
    folder = PRACTICE / name
    path = folder / "practice.json"
    if not path.is_file():
        raise CaseError(f"no practice repo named {name} (looked for {path})")
    data = json.loads(path.read_text())
    data["dir"] = folder
    if data.get("base"):
        data["base_practice"] = load_practice(data["base"])
    return data


def practice_names():
    return sorted(path.parent.name for path in PRACTICE.glob("*/practice.json"))


def load_case(name):
    """An eval case: its prompt, prompt settings, case.yaml text, run.json, and graders."""
    folder = CASES / name
    prompt_path = folder / "prompt.md"
    if not prompt_path.is_file():
        raise CaseError(f"no case named {name} (looked for {prompt_path})")
    settings, prompt = frontmatter(prompt_path.read_text())
    run_path = folder / "run.json"
    if not run_path.is_file():
        raise CaseError(f"{name}: run.json is missing; it names the practice repo and the graders")
    run = json.loads(run_path.read_text())
    if run.get("prepare", "bare") not in PREPARE_LEVELS:
        raise CaseError(f"{name}: prepare must be one of {PREPARE_LEVELS}")
    graders = sorted(path.name for path in (folder / "graders").glob("*.md")) if (folder / "graders").is_dir() else []
    return {
        "name": name, "dir": folder, "prompt": prompt.strip(), "settings": settings, "run": run,
        "tags": settings.get("tags", []), "grader_files": graders, "practice": load_practice(run["practice"]),
    }


def case_names():
    return sorted(path.parent.name for path in CASES.glob("*/prompt.md"))


def select_cases(patterns=(), tags=()):
    """The cases whose name matches any pattern (all when none) and that carry every tag given."""
    chosen = []
    for name in case_names():
        if patterns and not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            continue
        case = load_case(name)
        if tags and not all(tag in case["tags"] for tag in tags):
            continue
        chosen.append(case)
    return chosen
