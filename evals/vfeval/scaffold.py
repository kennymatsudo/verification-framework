"""Build a workspace for a case: the practice repo as a Git repository, and whatever the case says was already done.

Three levels of preparation:

- bare: the app's repo and nothing else (setup cases start here).
- ready: the hidden reference harness is installed, synced with the framework, its doctor proven, and committed, with
  zero feature coverage (add-checks cases start here).
- verified: the reference checks and feature map are added, every check and every hidden break has run through the
  framework, and the evidence is committed (verify, audit, and explain cases start here).

A change named in the case is applied on a branch as the developer's commit. Nothing under hidden/ is ever copied
into the workspace: the hidden breaks, the answer sheet, and practice.json stay outside the agent's view.
"""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import FRAMEWORK, VF

GIT_IDENTITY = ["-c", "user.name=Practice Developer", "-c", "user.email=dev@example.com"]


class ScaffoldError(Exception):
    pass


def git(path, *args, check=True):
    result = subprocess.run(["git", "-C", str(path), *GIT_IDENTITY, *args], capture_output=True, text=True)
    if check and result.returncode:
        raise ScaffoldError(f"git {' '.join(args)} in {path}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def copy_tree(source, target):
    """Copy source over target, file by file, so overlays merge instead of replacing folders."""
    for path in source.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        destination = target / path.relative_to(source)
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def shell(command, cwd, env=None, timeout=120):
    """Run a settings.md-style shell command from cwd; (exit code, combined output)."""
    merged = dict(os.environ, **(env or {}))
    try:
        result = subprocess.run(command, shell=True, cwd=str(cwd), env=merged, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {command}"
    return result.returncode, result.stdout + result.stderr


def hidden(practice, *parts):
    """A path under the practice's hidden folder, falling back to its base practice's."""
    path = practice["dir"].joinpath("hidden", *parts)
    if not path.exists() and practice.get("base_practice"):
        return hidden(practice["base_practice"], *parts)
    return path


def repo_sources(practice):
    """The repo folders to copy, base first, so an overlay practice adds to its base."""
    sources = []
    if practice.get("base_practice"):
        sources += repo_sources(practice["base_practice"])
    if (practice["dir"] / "repo").is_dir():
        sources.append(practice["dir"] / "repo")
    return sources


def harness_dir(practice, workspace):
    return workspace / practice["project_root"] / practice["harness"]


def project_root(practice, workspace):
    return workspace / practice["project_root"]


def framework_vf(practice, workspace):
    return harness_dir(practice, workspace) / "scripts" / "framework" / "vf.py"


def setting(harness, label):
    """A labeled command from the harness's settings.md Commands section, or None."""
    for line in (harness / "settings.md").read_text().splitlines():
        if line.startswith(f"- {label}:"):
            value = line.split(":", 1)[1].strip()
            return None if value.lower() == "none" else value
    return None


def harness_hashes(harness):
    """SHA-256 of every harness file an agent might weaken: scripts outside framework/, features, settings."""
    hashes = {}
    for path in sorted(harness.rglob("*")):
        if not path.is_file() or "framework" in path.relative_to(harness).parts or "evidence" in path.relative_to(harness).parts:
            continue
        rel = path.relative_to(harness).as_posix()
        if rel.startswith(("scripts/", "features/")) or rel == "settings.md":
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def feature_ids(harness):
    """Every sub-feature ID in the harness's feature map."""
    ids = []
    for path in sorted((harness / "features").glob("*.md")):
        if path.name == "README.md":
            continue
        in_section = False
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                in_section = line.strip() == "## Sub-features"
            elif in_section and line.startswith("- ") and ":" in line:
                ids.append(line[2:].split(":", 1)[0].strip())
    return ids


def proof_command(harness, sub_id):
    """The backticked check command on a sub-feature's How to prove it line, or None."""
    for path in (harness / "features").glob("*.md"):
        in_section = False
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                in_section = line.strip() == "## How to prove it"
            elif in_section and line.startswith(f"- {sub_id}:") and "`" in line:
                return line.split("`")[1]
    return None


def start_app(practice, workspace, log):
    harness = harness_dir(practice, workspace)
    command = setting(harness, "Start")
    if not command:
        return
    code, output = shell(command, project_root(practice, workspace))
    log.append(f"$ {command}\n{output}")
    if code:
        raise ScaffoldError(f"Start failed ({code}):\n{output}")


def stop_app(practice, workspace, log):
    harness = harness_dir(practice, workspace)
    command = setting(harness, "Stop")
    if command:
        code, output = shell(command, project_root(practice, workspace))
        log.append(f"$ {command}\n{output}")


def run_doctor(practice, workspace, log):
    harness = harness_dir(practice, workspace)
    code, output = shell(setting(harness, "Doctor"), project_root(practice, workspace))
    log.append(f"$ doctor -> {code}\n{output}")
    return code, output


def prove_doctor(practice, workspace, log):
    """Start the app, save the doctor's ready output, stop it, and confirm the doctor then says not ready."""
    harness = harness_dir(practice, workspace)
    (harness / "evidence" / "doctor").mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if setting(harness, "Start") is None:
        code, output = run_doctor(practice, workspace, log)
        if code:
            raise ScaffoldError(f"the reference doctor is not ready:\n{output}")
        proof = [f"# Doctor proof recorded by the eval scaffold at {stamp}", "", "## Nothing to start: the doctor on this checkout (exit 0)", output]
        (harness / "evidence" / "doctor" / "setup.txt").write_text("\n".join(proof) + "\n")
        return
    start_app(practice, workspace, log)
    try:
        code, output = run_doctor(practice, workspace, log)
        if code:
            raise ScaffoldError(f"the reference doctor is not ready after Start:\n{output}")
        proof = [f"# Doctor proof recorded by the eval scaffold at {stamp}", "", "## After Start (exit 0)", output]
    finally:
        stop_app(practice, workspace, log)
    code, output = run_doctor(practice, workspace, log)
    if code != 1:
        raise ScaffoldError(f"the reference doctor should exit 1 after Stop, got {code}:\n{output}")
    proof += ["", "## After Stop (exit 1)", output]
    (harness / "evidence" / "doctor" / "setup.txt").write_text("\n".join(proof) + "\n")


def install_harness(practice, workspace, log):
    """Overlay the hidden reference harness, sync the framework into it, and prove its doctor."""
    source = hidden(practice, "harness")
    if not source.is_dir():
        raise ScaffoldError(f"{practice['name']} has no hidden/harness to install")
    copy_tree(source, workspace)
    harness = harness_dir(practice, workspace)
    code, output = shell(f"{shlex.quote(sys.executable)} {shlex.quote(str(VF))} sync {shlex.quote(str(harness))}", workspace)
    log.append(f"$ vf.py sync\n{output}")
    if code:
        raise ScaffoldError(f"vf.py sync failed ({code}):\n{output}")
    prove_doctor(practice, workspace, log)
    code, output = shell(f"{shlex.quote(sys.executable)} {shlex.quote(str(framework_vf(practice, workspace)))} status", project_root(practice, workspace))
    log.append(f"$ vf.py status\n{output}")
    code, output = shell(f"{shlex.quote(sys.executable)} {shlex.quote(str(framework_vf(practice, workspace)))} validate --run-help", project_root(practice, workspace))
    log.append(f"$ vf.py validate --run-help\n{output}")
    if code:
        raise ScaffoldError(f"the reference harness does not validate ({code}):\n{output}")


def run_reference_checks(practice, workspace, log):
    """Run every mapped check once, then every hidden break through a break session, so the evidence is real."""
    harness = harness_dir(practice, workspace)
    root = project_root(practice, workspace)
    vf = f"{shlex.quote(sys.executable)} {shlex.quote(str(framework_vf(practice, workspace)))}"
    ids = feature_ids(harness)
    start_app(practice, workspace, log)
    try:
        code, output = shell(f"{vf} verify {' '.join(ids)}", root, timeout=300)
        log.append(f"$ vf.py verify {' '.join(ids)} -> {code}\n{output}")
        if code == 2:
            raise ScaffoldError(f"the reference checks could not run:\n{output}")
        scratch_command = setting(harness, "Run scratch code")
        if scratch_command and scratch_command.lower() != "per check":
            # One break session per repo: break run restores the scratch copy after each run, so the breaks for a
            # repo share a session and the app restarts once per break instead of three times.
            by_repo = {}
            for brk in practice.get("breaks", []):
                if proof_command(harness, brk["sub_feature"]):
                    by_repo.setdefault(brk.get("repo") or next(iter(practice["repos"])), []).append(brk)
            for repo, breaks in by_repo.items():
                code, output = shell(f"{vf} break start {shlex.quote(repo)}", root)
                log.append(f"$ vf.py break start {repo} -> {code}\n{output}")
                if code:
                    raise ScaffoldError(f"break start failed:\n{output}")
                scratch = next(line.split(" in ", 1)[1].split(",")[0].strip() for line in output.splitlines() if "uncommitted edit in" in line)
                try:
                    for brk in breaks:
                        command = proof_command(harness, brk["sub_feature"])
                        git(scratch, "apply", str(hidden(practice, brk["patch"])))
                        code, output = shell(f"{vf} break run {shlex.quote(repo)} {shlex.quote(brk['sub_feature'] + ': ' + brk['what'])} -- {shlex.quote(sys.executable)} {shlex.quote(str(framework_vf(practice, workspace)))} run -- {command}", root, timeout=300)
                        log.append(f"$ vf.py break run {brk['sub_feature']} -> {code}\n{output}")
                        if code:
                            raise ScaffoldError(f"break run for {brk['sub_feature']} failed:\n{output}")
                finally:
                    code, output = shell(f"{vf} break end {shlex.quote(repo)}", root)
                    log.append(f"$ vf.py break end -> {code}\n{output}")
    finally:
        stop_app(practice, workspace, log)
    code, output = shell(f"{vf} status", root)
    log.append(f"$ vf.py status -> {code}\n{output}")


def commit_all(repo, message):
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain"):
        git(repo, "commit", "-q", "-m", message)


def repos_of(practice, workspace):
    """{name: path} of every Git repo the practice declares, from the workspace root."""
    return {name: workspace / rel for name, rel in practice.get("git_repos", {".": "."}).items()} if isinstance(practice.get("git_repos"), dict) \
        else {rel: workspace / rel for rel in practice.get("git_repos", ["."])}


def scaffold(practice, into, prepare="bare", change=None, log=None):
    """Build the workspace at `into`; return a manifest of what was built. Raises ScaffoldError."""
    log = log if log is not None else []
    workspace = Path(into).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if any(workspace.iterdir()):
        raise ScaffoldError(f"{workspace} is not empty")
    for source in repo_sources(practice):
        copy_tree(source, workspace)
    repos = repos_of(practice, workspace)
    for path in repos.values():
        git(path, "init", "-q", "-b", "main")
        commit_all(path, "Initial import")
    manifest = {"practice": practice["name"], "prepare": prepare, "change": change, "workspace": str(workspace),
                "repos": {name: {"path": str(path.relative_to(workspace)), "head": git(path, "rev-parse", "HEAD")} for name, path in repos.items()},
                "harness": None, "harness_hashes": {}, "ports": practice.get("ports", [])}
    if prepare in ("ready", "verified"):
        install_harness(practice, workspace, log)
        root = project_root(practice, workspace)
        repo = git(root, "rev-parse", "--show-toplevel")
        commit_all(repo, "Add the verification harness")
        if prepare == "verified":
            coverage = hidden(practice, "coverage")
            if coverage.is_dir():
                copy_tree(coverage, workspace)
            run_reference_checks(practice, workspace, log)
            commit_all(repo, "Add feature checks and record their runs")
        manifest["harness"] = str(harness_dir(practice, workspace).relative_to(workspace))
        manifest["harness_hashes"] = harness_hashes(harness_dir(practice, workspace))
    if change:
        spec = practice.get("changes", {}).get(change)
        if not spec:
            raise ScaffoldError(f"{practice['name']} has no change named {change}")
        repo = workspace / practice["project_root"] if "repo" not in spec else repos[spec["repo"]]
        repo = Path(git(repo, "rev-parse", "--show-toplevel"))
        git(repo, "checkout", "-q", "-b", spec["branch"])
        git(repo, "apply", str(hidden(practice, spec["patch"])))
        commit_all(repo, spec["message"])
        manifest["change_commit"] = git(repo, "rev-parse", "HEAD")
    for name, path in repos.items():
        manifest["repos"][name]["head"] = git(path, "rev-parse", "HEAD")
    manifest["log"] = log
    return manifest


def write_manifest(manifest, path):
    Path(path).write_text(json.dumps(manifest, indent=2) + "\n")
