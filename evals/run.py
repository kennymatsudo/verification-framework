#!/usr/bin/env python3
"""Run the skills evaluation suite: practice repos, cases, an agent with a simulated developer, and graders.

Usage:
  run.py list                                  the cases, their tags, and their practice repos
  run.py fixtures [--practice NAME ...]        tier 0: prove the practice repos and cases are sound (no agent)
  run.py run [--case GLOB ...] [--tag TAG ...] [--runs N] [--model M] [--user-model M] [--keep] [--out DIR]
                                               tier 1: run cases against the skills with a headless agent, then grade
  run.py scaffold --case NAME --into DIR       build a case's workspace (what scaffold.sh does for claude plugin eval)
  run.py scaffold --practice NAME --prepare LEVEL [--change NAME] --into DIR
  run.py grade DIR --case NAME                 grade an existing workspace again (turns.json beside it if present)

Results go under evals/results/<time>/<case>/run-<n>/: turns.json, transcript.md, grading.json, manifest.json,
and the workspace when --keep is set. summary.json and summary.md sit at the top. Exit 0 when every case passed
every run, 1 when any did not, 2 when nothing could run.
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfeval import RESULTS, agent, cases, fixtures, graders, report, scaffold  # noqa: E402


def cmd_list(args):
    for case in cases.select_cases(args.case, args.tag):
        run = case["run"]
        print(f"{case['name']:32} {case['practice']['name']:14} {run.get('prepare', 'bare'):9} {','.join(case['tags'])}")
    return 0


def cmd_fixtures(args):
    problems = fixtures.check_cases()
    for problem in problems:
        print(f"CASE  {problem}")
    names = args.practice or cases.practice_names()
    for name in names:
        started = time.perf_counter()
        practice = cases.load_practice(name)
        found = fixtures.check_practice(practice, keep=args.keep)
        print(f"{'ok  ' if not found else 'FAIL'} {time.perf_counter() - started:5.1f}s  {name}")
        for problem in found:
            print(f"      {problem}")
        problems += found
    return 1 if problems else 0


def cmd_scaffold(args):
    if args.case:
        case = cases.load_case(args.case)
        practice, prepare, change = case["practice"], case["run"].get("prepare", "bare"), case["run"].get("change")
    else:
        practice, prepare, change = cases.load_practice(args.practice), args.prepare, args.change
    manifest = scaffold.scaffold(practice, args.into, prepare=prepare, change=change)
    if args.manifest:
        scaffold.write_manifest(manifest, args.manifest)
    print(f"scaffolded {practice['name']} ({prepare}{', ' + change if change else ''}) at {manifest['workspace']}")
    return 0


def load_sheet(case):
    sheet = json.loads(scaffold.hidden(case["practice"], "answers.json").read_text()) if scaffold.hidden(case["practice"], "answers.json").is_file() else {"rules": [], "default": "Go ahead."}
    extra = case["run"].get("answers", {})
    sheet = dict(sheet)
    sheet["rules"] = extra.get("rules", []) + sheet.get("rules", [])
    sheet["facts"] = extra.get("facts", []) + sheet.get("facts", [])
    sheet["default"] = extra.get("default", sheet.get("default"))
    return sheet


CACHE = {}


def scaffold_cached(case, workspace):
    """Build each (practice, level, change) once per invocation and copy it for every run that needs it."""
    key = (case["practice"]["name"], case["run"].get("prepare", "bare"), case["run"].get("change"))
    if key not in CACHE:
        built = Path(tempfile.mkdtemp(prefix="vf-eval-cache-"))
        CACHE[key] = (built, scaffold.scaffold(case["practice"], built, prepare=key[1], change=key[2]))
    built, manifest = CACHE[key]
    workspace.rmdir()
    shutil.copytree(built, workspace, symlinks=True)
    return dict(manifest, workspace=str(workspace), log=[])


def run_case_once(case, out_dir, args):
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"vf-eval-{case['name']}-"))
    run_record = {"case": case["name"], "score": 0.0, "graders": [], "cost_usd": 0.0, "duration_s": 0.0, "error": None}
    started = time.perf_counter()
    try:
        manifest = scaffold_cached(case, workspace)
        scaffold.write_manifest(manifest, out_dir / "manifest.json")
        cwd = workspace / case["run"].get("cwd", ".")
        turns = agent.converse(case["prompt"], cwd, load_sheet(case), max_user_turns=case["run"].get("max_user_turns", 6),
                               user_model=args.user_model, timeout=case["settings"].get("timeout_seconds", 1800),
                               model=args.model, max_turns=case["settings"].get("max_turns", 80))
        report.write_json(out_dir / "turns.json", turns)
        (out_dir / "transcript.md").write_text(agent.transcript_lines(turns))
        run_record["cost_usd"] = round(sum(t["cost_usd"] for t in turns), 4)
        run_record["user_turns"] = len(turns) - 1
        run_record["agent_steps"] = sum(t["num_turns"] for t in turns)
        if turns and turns[-1].get("error"):
            run_record["error"] = turns[-1]["error"]
        ctx = graders.Context(workspace, case["practice"], case, manifest, turns)
        results, score = graders.grade(ctx, case["run"].get("graders", []))
        run_record["graders"], run_record["score"] = results, round(score, 3)
    except scaffold.ScaffoldError as error:
        run_record["error"] = f"scaffold: {error}"
    finally:
        run_record["duration_s"] = round(time.perf_counter() - started, 1)
        if args.keep:
            shutil.move(str(workspace), str(out_dir / "workspace"))
            run_record["workspace"] = str(out_dir / "workspace")
        else:
            shutil.rmtree(workspace, ignore_errors=True)
    report.write_json(out_dir / "grading.json", run_record)
    return run_record


def cmd_run(args):
    chosen = cases.select_cases(args.case, args.tag)
    if not chosen:
        print("STOPPED: no case matches", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else RESULTS / time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    out.mkdir(parents=True, exist_ok=True)
    print(f"results in {out}")
    case_results = {}
    for case in chosen:
        for number in range(1, args.runs + 1):
            record = run_case_once(case, out / case["name"] / f"run-{number}", args)
            case_results.setdefault(case["name"], []).append(record)
            failed = [g["name"] for g in record["graders"] if not g["passed"]]
            print(f"{'ok  ' if record['score'] >= 0.999 else 'FAIL'} {record['duration_s']:6.0f}s ${record['cost_usd']:5.2f}  {case['name']} run {number}: {record['score']:.2f}"
                  + (f"  failed: {', '.join(failed)}" if failed else "") + (f"  error: {record['error']}" if record["error"] else ""))
    for built, _ in CACHE.values():
        shutil.rmtree(built, ignore_errors=True)
    summary = report.summarize(case_results)
    report.write_json(out / "summary.json", summary)
    (out / "summary.md").write_text(report.markdown(summary))
    print(f"\n{summary['cases_all_passed']}/{summary['cases_total']} cases passed every run; mean {summary['mean_score']:.2f}; ${summary['cost_usd']:.2f}; see {out / 'summary.md'}")
    return 0 if summary["cases_all_passed"] == summary["cases_total"] else 1


def cmd_grade(args):
    case = cases.load_case(args.case)
    workspace = Path(args.workspace).resolve()
    beside = workspace.parent
    manifest = json.loads((beside / "manifest.json").read_text()) if (beside / "manifest.json").is_file() else {}
    turns = json.loads((beside / "turns.json").read_text()) if (beside / "turns.json").is_file() else []
    ctx = graders.Context(workspace, case["practice"], case, manifest, turns)
    results, score = graders.grade(ctx, case["run"].get("graders", []))
    for result in results:
        print(f"{'ok  ' if result['passed'] else 'FAIL'} {result['score']:.2f} {result['name']}: {result['evidence'][:300]}")
    print(f"score {score:.2f}")
    return 0 if score >= 0.999 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog="\n".join(__doc__.splitlines()[2:]))
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("list"); p.add_argument("--case", action="append", default=[]); p.add_argument("--tag", action="append", default=[]); p.set_defaults(run=cmd_list)
    p = commands.add_parser("fixtures"); p.add_argument("--practice", action="append", default=[]); p.add_argument("--keep", action="store_true"); p.set_defaults(run=cmd_fixtures)
    p = commands.add_parser("scaffold"); p.add_argument("--case"); p.add_argument("--practice"); p.add_argument("--prepare", default="bare", choices=cases.PREPARE_LEVELS)
    p.add_argument("--change"); p.add_argument("--into", required=True); p.add_argument("--manifest"); p.set_defaults(run=cmd_scaffold)
    p = commands.add_parser("run"); p.add_argument("--case", action="append", default=[]); p.add_argument("--tag", action="append", default=[])
    p.add_argument("--runs", type=int, default=1); p.add_argument("--model"); p.add_argument("--user-model"); p.add_argument("--keep", action="store_true"); p.add_argument("--out"); p.set_defaults(run=cmd_run)
    p = commands.add_parser("grade"); p.add_argument("workspace"); p.add_argument("--case", required=True); p.set_defaults(run=cmd_grade)
    args = parser.parse_args()
    try:
        return args.run(args)
    except (cases.CaseError, scaffold.ScaffoldError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
