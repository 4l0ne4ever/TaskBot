#!/usr/bin/env python3
"""Re-aggregate run_eval JSON metrics after removing samples that hit extract_fn exceptions.

Keeps only sample ids *not* listed in top-level ``runtime_errors`` (same ids as
``sweep_policy_thresholds_offline`` uses for ``--exclude-runtime-errors``).
Per-sample ``scores`` from the original run are reused — no LLM calls.
"""
from __future__ import annotations

import argparse
import copy
import json
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


def _runtime_failed_ids(payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in payload.get("runtime_errors") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if sid is not None and str(sid).strip():
            out.add(str(sid))
    return out


def _pipeline_model_stats_from_details(details: list[dict[str, Any]]) -> dict[str, Any]:
    provenance_per_sample: list[dict[str, Any]] = []
    for d in details:
        prov = d.get("model_provenance")
        if isinstance(prov, dict):
            provenance_per_sample.append({"sample_id": d.get("id"), **prov})
    if not provenance_per_sample:
        return {"subset_note": "no model_provenance on retained samples"}
    total_primary = sum(int(p.get("primary_calls") or 0) for p in provenance_per_sample)
    total_fallback = sum(int(p.get("fallback_calls") or 0) for p in provenance_per_sample)
    total_rl = sum(int(p.get("rate_limited_calls") or 0) for p in provenance_per_sample)
    contam_samples = sum(1 for p in provenance_per_sample if p.get("contaminated"))
    model_mix: dict[str, int] = {}
    for p in provenance_per_sample:
        for mname, cnt in (p.get("models_used") or {}).items():
            model_mix[mname] = model_mix.get(mname, 0) + int(cnt)
    return {
        "primary_calls_total": total_primary,
        "fallback_calls_per_sample_total": total_fallback,
        "rate_limited_calls_total": total_rl,
        "samples_using_fallback": contam_samples,
        "samples_total_with_provenance": len(provenance_per_sample),
        "contaminated": contam_samples > 0,
        "model_mix": model_mix,
    }


def _per_sample_scores(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in details:
        sc = d.get("scores")
        if not isinstance(sc, dict):
            raise SystemExit(f"sample {d.get('id')!r} missing scores dict; cannot recompute")
        out.append(
            {
                "title": sc["title"],
                "assignee": sc["assignee"],
                "deadline": sc["deadline"],
                "conflict": sc["conflict"],
                "conflict_eval_skipped": sc.get("conflict_eval_skipped", False),
                "abstention": sc["abstention"],
                "calibration_bins": sc["calibration_bins"],
                "sample_id": d.get("id"),
                "category": d.get("category"),
            }
        )
    return out


def recompute(payload: dict[str, Any]) -> dict[str, Any]:
    bad = _runtime_failed_ids(payload)
    orig_details = [d for d in (payload.get("sample_details") or []) if isinstance(d, dict)]
    kept = [d for d in orig_details if str(d.get("id") or "") not in bad]

    per_sample = _per_sample_scores(kept)
    overall = aggregate(per_sample)

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for s in per_sample:
        by_cat.setdefault(str(s.get("category") or "unknown"), []).append(s)

    error_type_dist: dict[str, int] = {}
    for d in kept:
        for et in d.get("error_types") or []:
            error_type_dist[et] = error_type_dist.get(et, 0) + 1

    out = copy.deepcopy(payload)
    orig_notes = dict(payload.get("eval_notes") or {})
    orig_rt = payload.get("runtime_errors") or []
    orig_ds = dict(payload.get("dataset_info") or {})

    out["sample_details"] = kept
    out["runtime_errors"] = []
    out["runtime_error_count"] = 0
    out["runtime_error_kinds"] = {}
    out["overall"] = overall
    out["per_category"] = {cat: aggregate(items) for cat, items in sorted(by_cat.items())}
    out["error_type_distribution"] = dict(sorted(error_type_dist.items(), key=lambda x: -x[1]))
    out["aborted_early"] = False
    out["abort_reason"] = None
    out["abort_after_samples"] = None

    out["dataset_info"] = {
        **orig_ds,
        "total_samples": len(kept),
        "total_categories": len(by_cat),
    }

    out["eval_notes"] = {
        **orig_notes,
        "success_only_recompute": True,
        "success_only_excluded_runtime_ids_sorted": sorted(bad),
        "success_only_original_sample_details": len(orig_details),
        "success_only_original_runtime_error_count": len(orig_rt),
        "success_only_note": (
            "Metrics are over samples with no extract_fn exception only; "
            "compare total_samples to requested_samples for coverage."
        ),
    }

    if (out.get("method") or "") == "pipeline":
        ms = _pipeline_model_stats_from_details(kept)
        orig_ms = payload.get("model_stats") if isinstance(payload.get("model_stats"), dict) else {}
        if "strict_primary_mode" in orig_ms:
            ms["strict_primary_mode"] = orig_ms["strict_primary_mode"]
        out["model_stats"] = ms

    out["timestamp"] = datetime.now(timezone.utc).isoformat()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove runtime-failed samples from run_eval JSON and re-aggregate metrics",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write <output-stem>_report.md next to --output",
    )
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit("--input must be a JSON object")
    payload = recompute(raw)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    n_kept = len(payload.get("sample_details") or [])
    excl = (payload.get("eval_notes") or {}).get("success_only_excluded_runtime_ids_sorted") or []
    print(
        f"Wrote {args.output}  (kept {n_kept} success samples, dropped {len(excl)} runtime-error ids)",
        flush=True,
    )

    if args.write_report:
        from run_eval import _generate_report

        report_path = args.output.with_name(args.output.stem + "_report.md")
        _generate_report(payload, str(payload.get("method") or "pipeline"), report_path)
        print(f"Wrote {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
