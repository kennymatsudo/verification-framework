"""Tier 0: prove the practice repos and cases are sound without running any agent.

A practice repo is sound when its reference harness scaffolds, validates, and reports every reference-covered
behavior Verified (known bugs Failed), and when each hidden break, applied to the checkout, fails exactly its own
behavior's check and no other. A case is sound when its files load and name a practice, a level, and graders that
exist. This runs in seconds per repo, so it belongs in the unit test suite.
"""

import shlex
import sys
import tempfile
from pathlib import Path

from . import cases, graders, scaffold
from .cases import load_practice


def check_practice(practice, keep=False):
    """Problems found with one practice repo (empty when sound)."""
    problems, log = [], []
    levels = practice.get("fixture", {}).get("levels", ["verified"])
    tmp = Path(tempfile.mkdtemp(prefix=f"vf-fixture-{practice['name']}-"))
    try:
        for level in levels:
            workspace = tmp / level
            try:
                manifest = scaffold.scaffold(practice, workspace, prepare=level, log=log)
            except scaffold.ScaffoldError as error:
                problems.append(f"{level}: scaffold failed: {error}")
                continue
            for expect in practice.get("fixture", {}).get("expect", []):
                code, output = scaffold.shell(expect["run"], workspace / expect.get("cwd", "."), timeout=60)
                if code != expect.get("exit", 0) or (expect.get("output") and expect["output"] not in output):
                    problems.append(f"{level}: `{expect['run']}` exited {code} (wanted {expect.get('exit', 0)}); output: {output[-300:]}")
            if level != "verified":
                continue
            ctx = graders.Context(workspace, practice, None, manifest, [])
            code, output = ctx.run_vf("validate", "--require-evidence", "--run-help")
            if code:
                problems.append(f"verified: validate --require-evidence exit {code}:\n{output[-800:]}")
            verdicts = ctx.verdicts()
            covered = [sub_id for sub_id in practice["behaviors"] if scaffold.proof_command(ctx.harness, sub_id)]
            for sub_id in practice["behaviors"]:
                wanted = "Failed" if sub_id in practice.get("known_bugs", {}) else ("Verified" if sub_id in covered else None)
                actual = verdicts.get(sub_id, ("missing", ""))
                if wanted and actual[0] != wanted:
                    problems.append(f"verified: {sub_id} is {actual[0]} ({actual[1][:160]}), wanted {wanted}")
            problems += check_breaks(ctx, practice, covered)
            busy = graders.no_processes_left(ctx)
            if not busy.passed:
                problems.append(f"after the fixture run: {busy.evidence}")
    finally:
        if keep:
            problems.append(f"workspace kept at {tmp}")
        else:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    return problems


def check_breaks(ctx, practice, covered):
    """Apply each hidden break to the checkout; the behavior it targets must read Failed through the reference check.

    Only the target is judged: a broken deposit also breaks transfers that fund an account, and a check covering two
    behaviors fails both, so demanding that every other behavior stay Verified would reject sound fixtures."""
    problems = []
    repos = ctx.repos()
    expected_ok = [sub_id for sub_id in covered if sub_id not in practice.get("known_bugs", {})]
    if not expected_ok:
        return problems
    for brk in practice.get("breaks", []):
        patch = scaffold.hidden(practice, brk["patch"])
        if not patch.is_file():
            problems.append(f"break {brk['patch']} is missing")
            continue
        repo = repos[brk.get("repo", next(iter(repos)))]
        if scaffold.git(repo, "apply", "--check", str(patch), check=False) is None:
            problems.append(f"break {patch.name} does not apply to {repo.name}")
            continue
        if brk["sub_feature"] not in covered:
            problems.append(f"break {patch.name} targets {brk['sub_feature']}, which has no reference check")
            continue
        scaffold.git(repo, "apply", str(patch))
        try:
            started, output = ctx.start_app()
            if not started:
                problems.append(f"break {patch.name}: Start failed: {output[-300:]}")
                continue
            code, output = ctx.run_vf("verify", brk["sub_feature"], timeout=300)
            actual = ctx.verdicts(output).get(brk["sub_feature"], ("missing", ""))
            if actual[0] != "Failed":
                problems.append(f"break {patch.name} ({brk['what']}): {brk['sub_feature']} is {actual[0]} {actual[1][:120]}, wanted Failed")
        finally:
            ctx.stop_app()
            scaffold.git(repo, "apply", "-R", str(patch), check=False)
    return problems


def check_cases():
    """Problems with the case folders: files, settings, practices, levels, graders."""
    problems = []
    names = cases.case_names()
    if not names:
        problems.append("no cases found")
    for name in names:
        try:
            case = cases.load_case(name)
        except (cases.CaseError, ValueError) as error:
            problems.append(f"{name}: {error}")
            continue
        folder = case["dir"]
        if not (folder / "case.yaml").is_file():
            problems.append(f"{name}: case.yaml is missing")
        elif f"name: {name}" not in (folder / "case.yaml").read_text():
            problems.append(f"{name}: case.yaml does not name the case")
        if not case["grader_files"]:
            problems.append(f"{name}: graders/ has no .md grader (claude plugin eval refuses the case)")
        if not (folder / "scaffold.sh").is_file():
            problems.append(f"{name}: scaffold.sh is missing")
        if not case["prompt"]:
            problems.append(f"{name}: prompt.md has no prompt body")
        for key in ("max_turns", "timeout_seconds"):
            if key not in case["settings"]:
                problems.append(f"{name}: prompt.md frontmatter lacks {key}")
        run = case["run"]
        for spec in run.get("graders", []):
            if spec.get("name") not in graders.GRADERS:
                problems.append(f"{name}: unknown grader {spec.get('name')}")
        if not run.get("graders"):
            problems.append(f"{name}: run.json lists no graders")
        change = run.get("change")
        if change and change not in case["practice"].get("changes", {}):
            problems.append(f"{name}: change {change} is not declared by {case['practice']['name']}")
        if run.get("prepare", "bare") != "bare" and not scaffold.hidden(case["practice"], "harness").is_dir():
            problems.append(f"{name}: prepare {run['prepare']} needs {case['practice']['name']}/hidden/harness")
    return problems
