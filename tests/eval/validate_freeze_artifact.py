#!/usr/bin/env python3
"""Validate sweep freeze artifact integrity before release gating.

Checks:
  1) freeze artifact schema/status/chosen thresholds.
  2) chosen thresholds exist in sweep CSV.
  3) chosen row is clean (not contaminated) unless explicitly overridden.
  4) checkpoint (if present) is complete and includes chosen pair.
  5) optional eval-result consistency (policy version + thresholds).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_policy_version(value: Any) -> str:
    txt = str(value or "").strip().lower()
    if txt.startswith("policy_"):
        txt = txt[7:]
    return txt


def _coerce_path(path_like: str | None) -> Path | None:
    if not path_like:
        return None
    p = Path(path_like)
    return p if p.is_absolute() else ROOT / p


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return payload


def _row_matches(row: dict[str, Any], abstain: float, uncertain: float) -> bool:
    try:
        a = float(row.get("abstain"))
        u = float(row.get("uncertain"))
    except (TypeError, ValueError):
        return False
    eps = 1e-6
    return abs(a - abstain) <= eps and abs(u - uncertain) <= eps


def _parse_contaminated(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _validate_checkpoint(
    checkpoint_path: Path,
    *,
    abstain: float,
    uncertain: float,
) -> list[str]:
    issues: list[str] = []
    cp = _read_json(checkpoint_path)
    status = str(cp.get("status") or "").strip()
    if status != "complete":
        issues.append(f"checkpoint status must be 'complete' (got {status!r})")
    pairs = cp.get("completed_pairs") or []
    pair_key = [str(abstain), str(uncertain)]
    if pair_key not in pairs:
        # tolerate rounded formatting variants in old checkpoints
        alt = [f"{abstain:g}", f"{uncertain:g}"]
        if alt not in pairs:
            issues.append(
                "chosen threshold pair not present in checkpoint completed_pairs"
            )
    return issues


def _validate_eval_result(
    eval_path: Path,
    *,
    abstain: float,
    uncertain: float,
    freeze_policy_version: str,
) -> list[str]:
    issues: list[str] = []
    payload = _read_json(eval_path)
    effective = ((payload.get("policy") or {}).get("effective")) or {}
    got_a = effective.get("confidence_abstain_threshold")
    got_u = effective.get("confidence_uncertain_threshold")
    if got_a is None or got_u is None:
        issues.append("eval result missing policy.effective threshold values")
    else:
        eps = 1e-6
        if abs(float(got_a) - abstain) > eps:
            issues.append(f"eval abstain threshold mismatch: expected {abstain}, got {got_a}")
        if abs(float(got_u) - uncertain) > eps:
            issues.append(f"eval uncertain threshold mismatch: expected {uncertain}, got {got_u}")
    expected_policy = _normalize_policy_version(freeze_policy_version)
    got_policy = _normalize_policy_version(effective.get("pipeline_policy_version_key"))
    if expected_policy and got_policy and got_policy != expected_policy:
        issues.append(
            f"eval policy version mismatch: expected {expected_policy}, got {got_policy}"
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate freeze artifact integrity")
    parser.add_argument("--freeze-artifact", type=Path, required=True)
    parser.add_argument(
        "--allow-contaminated-freeze",
        action="store_true",
        help="Allow chosen row contaminated=true",
    )
    parser.add_argument(
        "--eval-result",
        type=Path,
        default=None,
        help="Optional eval result JSON to cross-check policy/threshold alignment",
    )
    args = parser.parse_args()

    freeze_path = (
        args.freeze_artifact
        if args.freeze_artifact.is_absolute()
        else ROOT / args.freeze_artifact
    )
    if not freeze_path.is_file():
        print(f"freeze artifact not found: {freeze_path}", flush=True)
        return 2

    freeze = _read_json(freeze_path)
    issues: list[str] = []
    status = str(freeze.get("status") or "").strip()
    if status != "complete":
        issues.append(f"freeze artifact status must be 'complete' (got {status!r})")

    chosen = freeze.get("chosen") or {}
    abstain = chosen.get("confidence_abstain_threshold")
    uncertain = chosen.get("confidence_uncertain_threshold")
    if abstain is None or uncertain is None:
        issues.append("freeze artifact missing chosen confidence thresholds")
        abstain = uncertain = 0.0
    abstain = float(abstain)
    uncertain = float(uncertain)

    csv_path = _coerce_path(str(freeze.get("csv_path") or "")) or freeze_path.with_suffix(".csv")
    if not csv_path.is_file():
        issues.append(f"sweep csv not found: {csv_path}")
        rows: list[dict[str, Any]] = []
    else:
        rows = _load_csv_rows(csv_path)
        match = next((r for r in rows if _row_matches(r, abstain, uncertain)), None)
        if match is None:
            issues.append(
                f"chosen thresholds not found in sweep csv row set: abstain={abstain}, uncertain={uncertain}"
            )
        else:
            contaminated = _parse_contaminated(match.get("contaminated"))
            allow_contam = args.allow_contaminated_freeze or _env_flag(
                "EVAL_ALLOW_CONTAMINATED_FREEZE", False
            )
            if contaminated and not allow_contam:
                issues.append(
                    "chosen sweep row is contaminated=true; rerun clean sweep or pass --allow-contaminated-freeze"
                )

    checkpoint_path = _coerce_path(str(freeze.get("checkpoint_path") or ""))
    if checkpoint_path is not None and checkpoint_path.is_file():
        issues.extend(
            _validate_checkpoint(checkpoint_path, abstain=abstain, uncertain=uncertain)
        )

    if args.eval_result is not None:
        eval_path = args.eval_result if args.eval_result.is_absolute() else ROOT / args.eval_result
        if not eval_path.is_file():
            issues.append(f"eval result not found: {eval_path}")
        else:
            issues.extend(
                _validate_eval_result(
                    eval_path,
                    abstain=abstain,
                    uncertain=uncertain,
                    freeze_policy_version=str(freeze.get("pipeline_policy_version") or ""),
                )
            )

    if issues:
        print("FREEZE VALIDATION FAILED", flush=True)
        for item in issues:
            print(f"- {item}", flush=True)
        return 2
    print("FREEZE VALIDATION PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
