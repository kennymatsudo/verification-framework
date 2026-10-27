"""Builders for the JSON files a harness carries, shared by the test files: harness.json and features/<slug>.json."""

import copy
import json

MANIFEST = {
    "app": "App",
    "setup": {
        "status": "ready",
        "target": "storefront",
        "findings": "README.md:4 documents startup",
        "looked_in": "README.md and scripts/dev",
        "blocker": None,
        "next": None,
        "doctor_proof": "evidence/doctor/2026-10-09T10-00-00Z.txt, 2026-10-09, app abc123",
    },
    "requirements": None,
    "repos": {"app": "."},
    "commands": {
        "start": "npm run dev",
        "stop": "npm run stop",
        "doctor": "bin/verify doctor",
        "ready_line": "verify: ready",
        "probe": None,
        "reloads": False,
    },
    "tools": {},
}


def manifest(**overrides):
    """A ready manifest with the top-level keys given replaced; a dict override for setup, commands, repos, or tools merges."""
    data = copy.deepcopy(MANIFEST)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict) and key in ("setup", "commands"):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return data


def write_manifest(harness, data=None, **overrides):
    """Write harness.json; returns the dict written."""
    data = data if data is not None else manifest(**overrides)
    (harness / "harness.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def read_manifest(harness):
    return json.loads((harness / "harness.json").read_text())


def edit_manifest(harness, change):
    """Apply change(data) to harness.json and write it back."""
    data = read_manifest(harness)
    change(data)
    return write_manifest(harness, data)


def feature(behaviors, name="Checkout", summary="A shopper pays for the items in their cart.", **extra):
    """A features/<slug>.json object."""
    return {"name": name, "summary": summary, "reach": ["Checkout button."], "behaviors": behaviors, **extra}


def write_feature(harness, slug, behaviors, **kwargs):
    """Write features/<slug>.json; returns the dict written."""
    data = feature(behaviors, **kwargs)
    (harness / "features").mkdir(exist_ok=True)
    (harness / "features" / f"{slug}.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def edit_feature(harness, slug, change):
    path = harness / "features" / f"{slug}.json"
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data
