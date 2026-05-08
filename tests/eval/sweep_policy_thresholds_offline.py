#!/usr/bin/env python3
"""Sweep confidence thresholds from a saved pipeline eval artifact.

This is the quota-safe companion to ``sweep_policy_thresholds.py``. Run
``run_eval.py`` once (full grid of ``(abstain, uncertain)`` is *not* needed):
pipeline eval should call Groq once per sample and persist candidate tasks in
``sample_details[*].prediction_meta.candidate_tasks``. This script replays the
full abstain×uncertain grid locally with no LLM calls. Use ``--exclude-runtime-errors``
(or ``EVAL_OFFLINE_EXCLUDE_RUNTIME_ERRORS``) to aggregate metrics only over
samples whose ids are absent from the artifact's ``runtime_errors`` list.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_AGENT = ROOT / "agent"
_EVAL = ROOT / "tests" / "eval"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))

from metrics import aggregate, evaluate_sample


def _grid(raw: str | None, default: str) -> list[str]:
    src = raw or default
    return [x.strip() for x in src.split(",") if x.strip()]


def _score(task: dict[str, Any]) -> float | None:
    raw = task.get("decision_score")
    if raw is None:
        raw = task.get("confidence")
    if isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw)))
    return None


def _apply_thresholds(candidates: list[dict], *, abstain: float, uncertain: float) -> list[dict]:
    out: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        score = _score(item)
        if score is None or score < abstain:
            continue
        row = dict(item)
        row["confidence"] = score
        row["decision_score"] = score
        row["decision_band"] = "uncertain" if score < uncertain else "accept"
        row["abstained"] = False
        out.append(row)
    return out


def _sample_for_conflict(detail: dict[str, Any]) -> dict[str, Any]:
    if detail.get("eval_existing_tasks_present"):
        return {"eval_existing_tasks": [{"id": "offline-fixture"}]}
    return {}


def _classify_errors(expected: dict[str, Any], predicted: dict[str, Any], scores: dict[str, Any]) -> list[str]:
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


def _candidate_tasks(detail: dict[str, Any]) -> list[dict]:
    meta = detail.get("prediction_meta") if isinstance(detail, dict) else None
    if isinstance(meta, dict) and isinstance(meta.get("candidate_tasks"), list):
        return [x for x in meta["candidate_tasks"] if isinstance(x, dict)]
    # Back-compat for older artifacts: use scored predictions as candidates.
    return [x for x in (detail.get("predicted_tasks") or []) if isinstance(x, dict)]


def _runtime_failed_ids(source: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in source.get("runtime_errors") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if sid is not None and str(sid).strip():
            out.add(str(sid))
    return out


def _details_for_metrics(
    source: dict[str, Any], *, exclude_runtime_errors: bool
) -> tuple[list[dict[str, Any]], int]:
    """Return (details_to_score, samples_excluded_runtime)."""
    all_details = [d for d in (source.get("sample_details") or []) if isinstance(d, dict)]
    if not exclude_runtime_errors:
        return all_details, 0
    bad = _runtime_failed_ids(source)
    kept = [d for d in all_details if str(d.get("id") or "") not in bad]
    return kept, len(all_details) - len(kept)


def _build_row(
    source: dict[str, Any],
    abstain: str,
    uncertain: str,
    *,
    exclude_runtime_errors: bool = False,
) -> dict[str, Any]:
    a = float(abstain)
    u = float(uncertain)
    per_sample = []
    errors = 0
    details, excluded_rt = _details_for_metrics(source, exclude_runtime_errors=exclude_runtime_errors)
    for detail in details:
        candidates = _candidate_tasks(detail)
        pred = {
            "tasks": _apply_thresholds(candidates, abstain=a, uncertain=u),
            "conflicts": detail.get("predicted_conflicts") or [],
            "missing_fields": [],
        }
        expected = {
            "tasks": detail.get("expected_tasks") or [],
            "conflicts": detail.get("expected_conflicts") or [],
        }
        scores = evaluate_sample(expected, pred, _sample_for_conflict(detail))
        if detail.get("error_types"):
            errors += 1
        per_sample.append(
            {
                "title": scores["title"],
                "assignee": scores["assignee"],
                "deadline": scores["deadline"],
                "conflict": scores["conflict"],
                "conflict_eval_skipped": scores.get("conflict_eval_skipped", False),
                "abstention": scores["abstention"],
                "calibration_bins": scores["calibration_bins"],
                "sample_id": detail.get("id"),
                "category": detail.get("category"),
            }
        )
    overall = aggregate(per_sample)
    abst = (overall.get("abstention") or {}).get("when_expected_empty") or {}
    cal = overall.get("calibration") or {}
    correct = sum(
        1 for s in per_sample
        if s["title"]["fp"] == 0
        and s["title"]["fn"] == 0
        and s["assignee"]["fp"] == 0
        and s["assignee"]["fn"] == 0
        and s["deadline"]["exact"] == s["deadline"]["total"]
        and s["conflict"]["fp"] == 0
        and s["conflict"]["fn"] == 0
    )
    total = len(per_sample)
    return {
        "abstain": a,
        "uncertain": u,
        "title_f1": overall.get("title_f1", {}).get("f1", 0),
        "deadline_exact": overall.get("deadline_exact", 0),
        "fully_correct_pct": round(100.0 * correct / total, 2) if total else 0.0,
        "correct_abstain_empty_gt": abst.get("correct_abstain_rate"),
        "false_answer_empty_gt": abst.get("false_answer_rate"),
        "ece": cal.get("ece"),
        "samples_completed": total,
        "samples_excluded_runtime": excluded_rt,
        "runtime_error_count": int(source.get("runtime_error_count") or 0),
        "aborted_early": bool(source.get("aborted_early")),
        "abort_reason": source.get("abort_reason") or "",
        "contaminated": bool((source.get("model_stats") or {}).get("contaminated") or source.get("aborted_early")),
        "contaminated_reason": "runtime_tpd" if source.get("abort_reason") == "daily_quota" else "",
        "sweep_mode": "offline",
    }


def _aligned_eval_result(
    source: dict[str, Any],
    *,
    abstain: float,
    uncertain: float,
    exclude_runtime_errors: bool = False,
) -> dict[str, Any]:
    sample_details: list[dict[str, Any]] = []
    per_sample_scores: list[dict[str, Any]] = []
    error_type_dist: dict[str, int] = {}

    details, _excluded = _details_for_metrics(source, exclude_runtime_errors=exclude_runtime_errors)
    for detail in details:
        predicted = {
            "tasks": _apply_thresholds(_candidate_tasks(detail), abstain=abstain, uncertain=uncertain),
            "conflicts": detail.get("predicted_conflicts") or [],
            "missing_fields": [],
        }
        expected = {
            "tasks": detail.get("expected_tasks") or [],
            "conflicts": detail.get("expected_conflicts") or [],
        }
        scores = evaluate_sample(expected, predicted, _sample_for_conflict(detail))
        error_types = _classify_errors(expected, predicted, scores)
        for et in error_types:
            error_type_dist[et] = error_type_dist.get(et, 0) + 1

        aligned_detail = dict(detail)
        aligned_detail.update(
            {
                "category": detail.get("category"),
                "language": detail.get("language"),
                "edge_tags": detail.get("edge_tags"),
                "input_excerpt": detail.get("input_excerpt") or "",
                "expected_task_count": len(expected["tasks"]),
                "predicted_task_count": len(predicted["tasks"]),
                "expected_tasks": expected["tasks"],
                "predicted_tasks": predicted["tasks"],
                "expected_conflicts": expected["conflicts"],
                "predicted_conflicts": predicted["conflicts"],
                "scores": scores,
                "error_types": error_types,
                "is_correct": len(error_types) == 0,
            }
        )
        sample_details.append(aligned_detail)
        per_sample_scores.append(
            {
                "title": scores["title"],
                "assignee": scores["assignee"],
                "deadline": scores["deadline"],
                "conflict": scores["conflict"],
                "conflict_eval_skipped": scores.get("conflict_eval_skipped", False),
                "abstention": scores["abstention"],
                "calibration_bins": scores["calibration_bins"],
                "sample_id": detail.get("id"),
                "category": detail.get("category"),
            }
        )

    overall = aggregate(per_sample_scores)
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in per_sample_scores:
        by_cat.setdefault(str(item.get("category") or "unknown"), []).append(item)

    policy = dict(source.get("policy") or {})
    policy["policy_threshold_overrides"] = {
        "abstain": str(abstain),
        "uncertain": str(uncertain),
    }
    effective = dict(policy.get("effective") or {})
    effective["confidence_abstain_threshold"] = abstain
    effective["confidence_uncertain_threshold"] = uncertain
    policy["effective"] = effective

    eval_notes = dict(source.get("eval_notes") or {})
    eval_notes["offline_aligned_from"] = "candidate_tasks"
    eval_notes["offline_source_eval_result"] = source.get("source_eval_result")
    if exclude_runtime_errors:
        eval_notes["offline_excluded_runtime_sample_ids"] = sorted(_runtime_failed_ids(source))

    dataset_info = dict(source.get("dataset_info") or {})
    dataset_info["total_samples"] = len(sample_details)
    dataset_info["total_categories"] = len(by_cat)

    return {
        **source,
        "policy": policy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_info": dataset_info,
        "eval_notes": eval_notes,
        "overall": overall,
        "per_category": {cat: aggregate(items) for cat, items in sorted(by_cat.items())},
        "error_type_distribution": dict(sorted(error_type_dist.items(), key=lambda x: -x[1])),
        "sample_details": sample_details,
    }


def _pick_best(rows: list[dict[str, Any]], cost_fp: float) -> dict[str, Any] | None:
    clean = [r for r in rows if not r.get("contaminated")]
    candidates = clean or rows
    best = None
    best_key = (-1.0, -1.0, -1.0)
    for row in candidates:
        tf = float(row.get("title_f1") or 0.0)
        fa = float(row.get("false_answer_empty_gt") or 0.0)
        fcp = float(row.get("fully_correct_pct") or 0.0)
        key = (tf - cost_fp * fa, tf, fcp)
        if key > best_key:
            best_key = key
            best = row
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline threshold sweep from one saved eval artifact")
    parser.add_argument("--result", type=Path, required=True, help="Pipeline eval JSON from run_eval.py")
    parser.add_argument("--output", type=Path, required=True, help="CSV path for offline sweep rows")
    parser.add_argument("--abstain", type=str, default=None)
    parser.add_argument("--uncertain", type=str, default=None)
    parser.add_argument("--write-freeze", type=Path, default=None)
    parser.add_argument(
        "--write-aligned-result",
        type=Path,
        default=None,
        help="Optional eval JSON recomputed at the selected thresholds without calling Groq.",
    )
    parser.add_argument(
        "--exclude-runtime-errors",
        action=argparse.BooleanOptionalAction,
        default=(os.getenv("EVAL_OFFLINE_EXCLUDE_RUNTIME_ERRORS") or "").strip().lower()
        in {"1", "true", "yes", "on"},
        help="Score only samples not listed in runtime_errors (clean subset). "
        "Default from EVAL_OFFLINE_EXCLUDE_RUNTIME_ERRORS.",
    )
    args = parser.parse_args()

    source = json.loads(args.result.read_text(encoding="utf-8"))
    source["source_eval_result"] = str(args.result)
    abstain_vals = _grid(args.abstain, os.getenv("EVAL_SWEEP_ABSTAIN_GRID", "0.55,0.6,0.65"))
    uncertain_vals = _grid(args.uncertain, os.getenv("EVAL_SWEEP_UNCERTAIN_GRID", "0.76,0.8,0.84"))
    excl = bool(args.exclude_runtime_errors)
    rows = [_build_row(source, a, u, exclude_runtime_errors=excl) for a in abstain_vals for u in uncertain_vals]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    cost_fp = float(os.getenv("EVAL_SWEEP_COST_FP_NO_TASK", "1"))
    best = _pick_best(rows, cost_fp)
    print(f"Wrote {len(rows)} offline rows to {args.output}")
    if best:
        print(
            f"Picked (offline): abstain={best['abstain']} uncertain={best['uncertain']} "
            f"title_f1={best.get('title_f1')} false_answer_empty_gt={best.get('false_answer_empty_gt')}"
        )
    if args.write_freeze and best:
        payload = {
            "status": "complete" if not source.get("aborted_early") else "partial",
            "sweep_mode": "offline",
            "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_eval_result": str(args.result),
            "pipeline_policy_version": (source.get("policy") or {}).get("pipeline_policy_version"),
            "chosen": {
                "confidence_abstain_threshold": best["abstain"],
                "confidence_uncertain_threshold": best["uncertain"],
                "metrics_snapshot": best,
            },
            "csv_path": str(args.output),
        }
        args.write_freeze.parent.mkdir(parents=True, exist_ok=True)
        args.write_freeze.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote offline freeze artifact {args.write_freeze}")
    if args.write_aligned_result and best:
        aligned = _aligned_eval_result(
            source,
            abstain=float(best["abstain"]),
            uncertain=float(best["uncertain"]),
            exclude_runtime_errors=excl,
        )
        args.write_aligned_result.parent.mkdir(parents=True, exist_ok=True)
        args.write_aligned_result.write_text(
            json.dumps(aligned, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote offline aligned eval result {args.write_aligned_result}")
        from run_eval import _generate_report

        report_path = args.write_aligned_result.with_name(
            f"{args.write_aligned_result.stem}_report.md"
        )
        _generate_report(aligned, str(aligned.get("method") or "pipeline"), report_path)
        print(f"Wrote offline aligned report {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
