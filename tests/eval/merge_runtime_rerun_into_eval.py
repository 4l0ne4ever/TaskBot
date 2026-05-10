#!/usr/bin/env python3
"""Merge a small pipeline run_eval JSON (rerun of runtime_error ids) into the main artifact.

Recomputes overall / per_category / error_type_distribution / model_stats like run_eval.
"""
from __future__ import annotations

import argparse
import copy
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

from metrics import aggregate

from run_eval import (  # noqa: E402
    _atomic_write_text,
    _eval_report_primary_model,
    _generate_report,
    _runtime_error_kinds,
)


def _reaggregate_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    sample_details: list[dict[str, Any]] = list(payload.get("sample_details") or [])
    error_type_dist: dict[str, int] = {}
    for d in sample_details:
        for et in d.get("error_types") or []:
            error_type_dist[et] = error_type_dist.get(et, 0) + 1

    provenance_per_sample: list[dict[str, Any]] = []
    for d in sample_details:
        prov = d.get("model_provenance")
        if isinstance(prov, dict):
            provenance_per_sample.append({"sample_id": d.get("id"), **prov})

    per_sample_scores = [
        {
            "title": d["scores"]["title"],
            "assignee": d["scores"]["assignee"],
            "deadline": d["scores"]["deadline"],
            "conflict": d["scores"]["conflict"],
            "conflict_eval_skipped": d["scores"].get("conflict_eval_skipped", False),
            "abstention": d["scores"]["abstention"],
            "calibration_bins": d["scores"]["calibration_bins"],
            "sample_id": d["id"],
            "category": d["category"],
        }
        for d in sample_details
    ]
    overall = aggregate(per_sample_scores)
    _counts = overall.get("counts") or {}

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for s in per_sample_scores:
        by_cat.setdefault(str(s.get("category") or "unknown"), []).append(s)

    method = str(payload.get("method") or "pipeline")
    model_stats: dict[str, Any] = {}
    if method == "pipeline":
        prev_ms = payload.get("model_stats") if isinstance(payload.get("model_stats"), dict) else {}
        model_stats = {"fallback_calls": int(prev_ms.get("fallback_calls") or 0)}
        if provenance_per_sample:
            total_primary = sum(int(p.get("primary_calls") or 0) for p in provenance_per_sample)
            total_fallback = sum(int(p.get("fallback_calls") or 0) for p in provenance_per_sample)
            total_rl = sum(int(p.get("rate_limited_calls") or 0) for p in provenance_per_sample)
            contam_samples = sum(1 for p in provenance_per_sample if p.get("contaminated"))
            model_mix: dict[str, int] = {}
            for p in provenance_per_sample:
                for mname, cnt in (p.get("models_used") or {}).items():
                    model_mix[mname] = model_mix.get(mname, 0) + int(cnt)
            prev = payload.get("model_stats") if isinstance(payload.get("model_stats"), dict) else {}
            strict = prev.get("strict_primary_mode")
            if strict is None:
                strict = (os.getenv("GROQ_STRICT_PRIMARY") or "").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            model_stats.update(
                {
                    "primary_calls_total": total_primary,
                    "fallback_calls_per_sample_total": total_fallback,
                    "rate_limited_calls_total": total_rl,
                    "samples_using_fallback": contam_samples,
                    "samples_total_with_provenance": len(provenance_per_sample),
                    "contaminated": contam_samples > 0,
                    "model_mix": model_mix,
                    "strict_primary_mode": strict,
                }
            )

    eval_notes = dict(payload.get("eval_notes") or {})
    eval_notes["conflict_eval_samples_skipped_for_metric"] = _counts.get("conflict_eval_samples_skipped")
    eval_notes["conflict_eval_samples_included_in_aggregate"] = _counts.get("conflict_eval_samples_scoped")

    rt = list(payload.get("runtime_errors") or [])
    out = {
        **payload,
        "eval_model": _eval_report_primary_model(method),
        "model_stats": model_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eval_notes": eval_notes,
        "overall": overall,
        "per_category": {cat: aggregate(items) for cat, items in sorted(by_cat.items())},
        "error_type_distribution": dict(sorted(error_type_dist.items(), key=lambda x: -x[1])),
        "runtime_errors": rt,
        "runtime_error_count": len(rt),
        "runtime_error_kinds": _runtime_error_kinds(rt),
        "sample_details": sample_details,
    }
    return out


def merge_main_with_rerun(
    main: dict[str, Any],
    rerun: dict[str, Any],
    *,
    rerun_path: str,
) -> dict[str, Any]:
    rerun_details = [d for d in (rerun.get("sample_details") or []) if isinstance(d, dict)]
    rerun_by_id = {str(d["id"]): d for d in rerun_details if d.get("id") is not None}
    rerun_ids = set(rerun_by_id.keys())
    if not rerun_ids:
        raise SystemExit("rerun JSON has no sample_details with id")

    main_details = [d for d in (main.get("sample_details") or []) if isinstance(d, dict)]
    merged: list[dict[str, Any]] = []
    replaced = 0
    for d in main_details:
        sid = str(d.get("id"))
        if sid in rerun_by_id:
            merged.append(copy.deepcopy(rerun_by_id[sid]))
            replaced += 1
        else:
            merged.append(d)

    if replaced != len(rerun_ids):
        raise SystemExit(
            f"rerun covers {len(rerun_ids)} ids but only {replaced} matched main sample_details"
        )

    old_rt = [e for e in (main.get("runtime_errors") or []) if isinstance(e, dict)]
    new_rt = [e for e in old_rt if str(e.get("id")) not in rerun_ids]
    new_rt.extend(e for e in (rerun.get("runtime_errors") or []) if isinstance(e, dict))

    payload = copy.deepcopy(main)
    payload["sample_details"] = merged
    payload["runtime_errors"] = new_rt

    notes = dict(payload.get("eval_notes") or {})
    notes["runtime_rerun_merge_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    notes["runtime_rerun_source"] = rerun_path
    notes["runtime_rerun_replaced_ids_sorted"] = sorted(rerun_ids)
    payload["eval_notes"] = notes

    return _reaggregate_pipeline(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge rerun JSON into main eval artifact")
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--rerun", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Default: overwrite --main")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    main_raw = json.loads(args.main.read_text(encoding="utf-8"))
    rerun_raw = json.loads(args.rerun.read_text(encoding="utf-8"))
    if not isinstance(main_raw, dict) or not isinstance(rerun_raw, dict):
        raise SystemExit("main and rerun must be JSON objects")

    out = merge_main_with_rerun(main_raw, rerun_raw, rerun_path=str(args.rerun.resolve()))
    out_path = args.output or args.main

    _atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"Wrote {out_path}  runtime_errors={out['runtime_error_count']} "
        f"kinds={out.get('runtime_error_kinds')}",
        flush=True,
    )

    if args.write_report:
        rp = out_path.with_name(out_path.stem + "_report.md")
        _generate_report(out, str(out.get("method") or "pipeline"), rp)
        print(f"Wrote {rp}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
