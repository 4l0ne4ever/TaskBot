#!/usr/bin/env python3
"""
Run evaluation of an extraction method against the labeled dataset.

Outputs:
  1. <output>.json         — full results (overall + per-category + per-sample details)
  2. <output>_report.md    — human-readable markdown report for thesis

Usage:
  python tests/eval/run_eval.py --method rule     --output tests/eval/results/rule.json
  python tests/eval/run_eval.py --method single   --output tests/eval/results/single_llm.json
  python tests/eval/run_eval.py --method pipeline  --output tests/eval/results/pipeline.json

  Optional: --dataset PATH  (default: tests/eval/labeled_dataset.json)
            --limit N        (only process first N samples)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tests" / "eval"))

from metrics import aggregate, evaluate_sample  # noqa: E402

DEFAULT_DATASET = Path(__file__).parent / "labeled_dataset.json"


def _load_dataset(path: Path, limit: int | None = None) -> list[dict]:
    data = json.loads(path.read_text("utf-8"))
    return data[:limit] if limit else data


def _run_rule_based(sample: dict) -> dict:
    from baselines.rule_based import extract_rule_based
    return extract_rule_based(sample["input_text"], sample.get("metadata") or {})


def _run_single_llm(sample: dict) -> dict:
    from baselines.single_llm import extract_single_llm
    return extract_single_llm(sample["input_text"], sample.get("metadata") or {})


def _run_pipeline(sample: dict) -> dict:
    from baselines.pipeline_runner import extract_pipeline
    return extract_pipeline(sample["input_text"], sample.get("metadata") or {})


METHODS = {
    "rule": _run_rule_based,
    "single": _run_single_llm,
    "pipeline": _run_pipeline,
}


def _classify_errors(sample: dict, expected: dict, predicted: dict, scores: dict) -> list[str]:
    """Classify what went wrong for error analysis."""
    issues = []
    if scores["title"]["fn"] > 0:
        issues.append("missed_task")
    if scores["title"]["fp"] > 0:
        issues.append("hallucinated_task")
    if scores["assignee"]["fn"] > 0:
        issues.append("missed_assignee")
    if scores["assignee"]["fp"] > 0:
        issues.append("wrong_assignee")
    if scores["deadline"]["total"] > 0 and scores["deadline"]["exact"] == 0:
        if scores["deadline"]["near"] > 0:
            issues.append("deadline_off_by_one")
        else:
            issues.append("wrong_deadline")
    if scores["conflict"]["fn"] > 0:
        issues.append("missed_conflict")
    if scores["conflict"]["fp"] > 0:
        issues.append("false_conflict")
    if not expected.get("tasks") and predicted.get("tasks"):
        issues.append("false_positive_extraction")
    if expected.get("tasks") and not predicted.get("tasks"):
        issues.append("complete_miss")
    return issues


def _build_sample_detail(sample: dict, prediction: dict, scores: dict, error_types: list[str]) -> dict:
    """Build a detailed per-sample record for the report."""
    return {
        "id": sample.get("id"),
        "category": sample.get("category"),
        "language": sample.get("language"),
        "edge_tags": sample.get("edge_tags"),
        "input_excerpt": sample["input_text"][:200] + ("..." if len(sample["input_text"]) > 200 else ""),
        "expected_task_count": len(sample["expected"].get("tasks") or []),
        "predicted_task_count": len(prediction.get("tasks") or []),
        "expected_tasks": sample["expected"].get("tasks") or [],
        "predicted_tasks": prediction.get("tasks") or [],
        "expected_conflicts": sample["expected"].get("conflicts") or [],
        "predicted_conflicts": prediction.get("conflicts") or [],
        "scores": scores,
        "error_types": error_types,
        "is_correct": len(error_types) == 0,
    }


def _generate_report(output: dict, method: str, report_path: Path):
    """Generate a detailed markdown report for thesis use."""
    lines = []
    lines.append(f"# Evaluation Report: {method}")
    lines.append(f"\nGenerated: {datetime.now().isoformat()[:19]}")
    lines.append(f"Dataset: {output['dataset_info']['total_samples']} samples, {output['dataset_info']['total_categories']} categories")
    lines.append(f"Errors (runtime): {output['runtime_error_count']}")

    lines.append("\n## 1. Overall Metrics\n")
    lines.append("| Metric | Precision | Recall | F1 |")
    lines.append("|--------|-----------|--------|----|")
    for field in ["title_f1", "assignee_f1", "conflict_f1"]:
        m = output["overall"][field]
        lines.append(f"| {field.replace('_f1','').capitalize()} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |")
    lines.append(f"\n| Metric | Score |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Deadline Exact Match | {output['overall']['deadline_exact']:.4f} |")
    lines.append(f"| Deadline Near (+-1d) | {output['overall']['deadline_near']:.4f} |")

    lines.append("\n## 2. Per-Category Breakdown\n")
    lines.append("| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |")
    lines.append("|----------|---------|----------|-------------|----------|---------|-------------|")
    for cat, data in sorted(output["per_category"].items()):
        n = data["counts"]["samples"]
        tf = data["title_f1"]["f1"]
        af = data["assignee_f1"]["f1"]
        de = data["deadline_exact"]
        dn = data["deadline_near"]
        cf = data["conflict_f1"]["f1"]
        lines.append(f"| {cat} | {n} | {tf:.4f} | {af:.4f} | {de:.4f} | {dn:.4f} | {cf:.4f} |")

    lines.append("\n## 3. Edge Case Performance\n")
    edge_cats = {c: d for c, d in output["per_category"].items() if c.startswith("edge_")}
    core_cats = {c: d for c, d in output["per_category"].items() if not c.startswith("edge_")}
    if edge_cats:
        core_tf = sum(d["title_f1"]["f1"] * d["counts"]["samples"] for d in core_cats.values()) / max(sum(d["counts"]["samples"] for d in core_cats.values()), 1)
        edge_tf = sum(d["title_f1"]["f1"] * d["counts"]["samples"] for d in edge_cats.values()) / max(sum(d["counts"]["samples"] for d in edge_cats.values()), 1)
        lines.append(f"- Core categories weighted Title F1: **{core_tf:.4f}**")
        lines.append(f"- Edge case categories weighted Title F1: **{edge_tf:.4f}**")
        lines.append(f"- Delta: **{edge_tf - core_tf:+.4f}**\n")

    lines.append("## 4. Error Analysis\n")
    err_dist = output.get("error_type_distribution") or {}
    if err_dist:
        lines.append("| Error Type | Count | % of Samples |")
        lines.append("|------------|-------|--------------|")
        total = output["overall"]["counts"]["samples"]
        for etype, cnt in sorted(err_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {etype} | {cnt} | {cnt/total*100:.1f}% |")

    lines.append("\n## 5. Per-Category Error Heatmap\n")
    cat_err: dict[str, dict[str, int]] = {}
    for detail in output.get("sample_details", []):
        cat = detail["category"]
        for et in detail.get("error_types", []):
            cat_err.setdefault(cat, {}).setdefault(et, 0)
            cat_err[cat][et] += 1
    all_err_types = sorted({et for ce in cat_err.values() for et in ce})
    if all_err_types:
        header = "| Category | " + " | ".join(all_err_types) + " |"
        sep = "|----------|" + "|".join(["---"] * len(all_err_types)) + "|"
        lines.append(header)
        lines.append(sep)
        for cat in sorted(cat_err.keys()):
            vals = " | ".join(str(cat_err[cat].get(et, 0)) for et in all_err_types)
            lines.append(f"| {cat} | {vals} |")

    lines.append("\n## 6. Sample-Level Details (Errors Only)\n")
    error_details = [d for d in output.get("sample_details", []) if not d["is_correct"]]
    for d in error_details[:50]:
        lines.append(f"### {d['id']} ({d['category']}, {d['language']})")
        if d.get("edge_tags"):
            lines.append(f"Edge tags: {', '.join(d['edge_tags'])}")
        lines.append(f"\n**Input:** {d['input_excerpt']}\n")
        lines.append(f"**Expected tasks:** {len(d['expected_tasks'])} | **Predicted:** {len(d['predicted_tasks'])}")
        if d["expected_tasks"]:
            for t in d["expected_tasks"]:
                lines.append(f"  - E: \"{t.get('title')}\" | {t.get('assignee')} | {t.get('deadline')} | pri={t.get('priority')}")
        if d["predicted_tasks"]:
            for t in d["predicted_tasks"]:
                lines.append(f"  - P: \"{t.get('title')}\" | {t.get('assignee')} | {t.get('deadline')} | pri={t.get('priority')}")
        lines.append(f"\n**Errors:** {', '.join(d['error_types'])}")
        lines.append(f"**Scores:** title={d['scores']['title']}, assignee={d['scores']['assignee']}, deadline={d['scores']['deadline']}, conflict={d['scores']['conflict']}")
        lines.append("")

    if len(error_details) > 50:
        lines.append(f"\n_...and {len(error_details) - 50} more error samples (see JSON for full details)._\n")

    lines.append(f"\n## 7. Summary Statistics\n")
    correct = sum(1 for d in output.get("sample_details", []) if d["is_correct"])
    total = len(output.get("sample_details", []))
    lines.append(f"- Fully correct samples: **{correct}/{total}** ({correct/total*100:.1f}%)")
    lines.append(f"- Samples with errors: **{total - correct}/{total}** ({(total-correct)/total*100:.1f}%)")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="TaskBot Extraction Evaluation")
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    samples = _load_dataset(args.dataset, args.limit)
    extract_fn = METHODS[args.method]

    sample_details = []
    runtime_errors = []
    error_type_dist: dict[str, int] = {}

    total = len(samples)
    for i, sample in enumerate(samples):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{total}] processing {sample.get('id')} ({sample.get('category')})...", flush=True)
        try:
            prediction = extract_fn(sample)
        except Exception as exc:
            runtime_errors.append({"index": i, "id": sample.get("id"), "error": str(exc)})
            prediction = {"tasks": [], "conflicts": [], "missing_fields": []}

        scores = evaluate_sample(sample["expected"], prediction)
        error_types = _classify_errors(sample, sample["expected"], prediction, scores)

        for et in error_types:
            error_type_dist[et] = error_type_dist.get(et, 0) + 1

        detail = _build_sample_detail(sample, prediction, scores, error_types)
        sample_details.append(detail)

    per_sample_scores = [
        {
            "title": d["scores"]["title"],
            "assignee": d["scores"]["assignee"],
            "deadline": d["scores"]["deadline"],
            "conflict": d["scores"]["conflict"],
            "sample_id": d["id"],
            "category": d["category"],
        }
        for d in sample_details
    ]
    overall = aggregate(per_sample_scores)

    by_cat: dict[str, list[dict]] = {}
    for s in per_sample_scores:
        by_cat.setdefault(s["category"], []).append(s)

    model_stats = {}
    if args.method == "single":
        try:
            from baselines.single_llm import get_model_stats
            model_stats = get_model_stats()
        except ImportError:
            pass
    elif args.method == "pipeline":
        try:
            from app.pipeline.llm import get_fallback_count
            model_stats = {"fallback_calls": get_fallback_count()}
        except ImportError:
            pass

    eval_model = os.environ.get("EVAL_GROQ_MODEL", "llama-3.3-70b-versatile")
    output = {
        "method": args.method,
        "eval_model": eval_model,
        "model_stats": model_stats,
        "timestamp": datetime.now().isoformat(),
        "dataset_info": {
            "path": str(args.dataset),
            "total_samples": len(samples),
            "total_categories": len(by_cat),
            "limit_applied": args.limit,
        },
        "overall": overall,
        "per_category": {cat: aggregate(items) for cat, items in sorted(by_cat.items())},
        "error_type_distribution": dict(sorted(error_type_dist.items(), key=lambda x: -x[1])),
        "runtime_errors": runtime_errors,
        "runtime_error_count": len(runtime_errors),
        "sample_details": sample_details,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = args.output.with_name(args.output.stem + "_report.md")
    _generate_report(output, args.method, report_path)

    print(f"Method: {args.method}  Model: {eval_model}  {model_stats if model_stats else ''}")
    print(f"Samples: {overall['counts']['samples']}  Runtime errors: {len(runtime_errors)}")
    print(f"Title F1:       {overall['title_f1']['f1']:.4f}  (P={overall['title_f1']['precision']:.4f} R={overall['title_f1']['recall']:.4f})")
    print(f"Assignee F1:    {overall['assignee_f1']['f1']:.4f}")
    print(f"Deadline Exact: {overall['deadline_exact']:.4f}")
    print(f"Deadline Near:  {overall['deadline_near']:.4f}")
    print(f"Conflict F1:    {overall['conflict_f1']['f1']:.4f}")
    correct = sum(1 for d in sample_details if d["is_correct"])
    print(f"Fully correct:  {correct}/{len(sample_details)} ({correct/len(sample_details)*100:.1f}%)")
    print(f"\nTop error types:")
    for et, cnt in sorted(error_type_dist.items(), key=lambda x: -x[1])[:5]:
        print(f"  {et}: {cnt}")
    print(f"\nJSON:   {args.output}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
