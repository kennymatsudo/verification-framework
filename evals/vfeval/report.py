"""Write a run's grading and a summary across cases and runs."""

import json
import statistics
from pathlib import Path


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, default=str) + "\n")


def summarize(case_results):
    """case_results: {case: [run dicts with score, cost_usd, duration_s, graders]} -> summary dict."""
    cases = []
    for name, runs in case_results.items():
        scores = [run["score"] for run in runs]
        grader_rows = {}
        for run in runs:
            for g in run["graders"]:
                row = grader_rows.setdefault(g["name"] + (f" {g['params']}" if g["params"] else ""), {"passed": 0, "runs": 0, "doc": g["doc"]})
                row["runs"] += 1
                row["passed"] += g["passed"]
        cases.append({
            "case": name, "runs": len(runs), "model": sorted({run.get("model") for run in runs if run.get("model")}),
            "served_models": sorted({m for run in runs for m in run.get("served_models", [])}), "mean_score": round(statistics.fmean(scores), 3) if scores else 0,
            "min_score": round(min(scores), 3) if scores else 0, "all_passed": all(s >= 0.999 for s in scores) and bool(scores),
            "cost_usd": round(sum(run.get("cost_usd", 0) for run in runs), 2),
            "duration_s": round(sum(run.get("duration_s", 0) for run in runs), 0),
            "graders": grader_rows, "errors": [run.get("error") for run in runs if run.get("error")],
        })
    return {
        "cases": cases,
        "models": sorted({m for c in cases for m in c["model"]}),
        "served_models": sorted({m for c in cases for m in c["served_models"]}),
        "mean_score": round(statistics.fmean(c["mean_score"] for c in cases), 3) if cases else 0,
        "cases_all_passed": sum(c["all_passed"] for c in cases), "cases_total": len(cases),
        "cost_usd": round(sum(c["cost_usd"] for c in cases), 2),
    }


def markdown(summary, title="Skills eval"):
    lines = [f"# {title}", "", f"Agent model: {', '.join(summary.get('models') or ['unknown'])}" + (f" (served: {', '.join(summary['served_models'])})" if summary.get("served_models") else "") + ".",
             "", f"Mean score {summary['mean_score']:.2f}; {summary['cases_all_passed']}/{summary['cases_total']} cases passed every run; ${summary['cost_usd']:.2f}.", "",
             "| Case | Model | Runs | Mean | Min | All runs pass | Cost | Time |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in summary["cases"]:
        lines.append(f"| {c['case']} | {', '.join(c['model']) or 'unknown'} | {c['runs']} | {c['mean_score']:.2f} | {c['min_score']:.2f} | {'yes' if c['all_passed'] else 'no'} | ${c['cost_usd']:.2f} | {int(c['duration_s'])}s |")
    for c in summary["cases"]:
        lines += ["", f"## {c['case']}", ""]
        for name, row in c["graders"].items():
            mark = "ok  " if row["passed"] == row["runs"] else "FAIL"
            lines.append(f"- {mark} {row['passed']}/{row['runs']} {name}: {row['doc']}")
        for error in c["errors"]:
            lines.append(f"- error: {error}")
    return "\n".join(lines) + "\n"
