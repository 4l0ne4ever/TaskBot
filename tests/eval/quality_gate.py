#!/usr/bin/env python3
"""Quality gate for CI / release (Q-07).

Reads an eval result JSON produced by ``run_eval.py`` and enforces regression
guardrails. Supports two configuration sources (both optional, latter wins
when both set to keep the existing env-first workflow intact):

1. **Environment variables** (``EVAL_MIN_TITLE_F1``, ``EVAL_MIN_DEADLINE_EXACT``,
   ``EVAL_MIN_NOISE_PRECISION``, ``EVAL_MAX_CALIBRATION_ECE``,
   ``EVAL_EXPECT_POLICY_ABSTAIN`` / ``EVAL_EXPECT_POLICY_UNCERTAIN``) — useful
   for ad-hoc runs and the existing CI config.
2. **Frozen artifact** (``--freeze-artifact``) written by
   ``sweep_policy_thresholds.py --write-freeze``. Pins policy thresholds to
   the sweep-chosen values and (by default) the sweep's own metric snapshot
   as the minimum, so a release cannot silently regress below the threshold
   that was measured at freeze time.

Exit code:
  0 — pass
  2 — at least one gate failed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _threshold(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


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


def _load_freeze(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to read --freeze-artifact {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"--freeze-artifact {path} is not a JSON object")
    chosen = data.get("chosen") or {}
    if not isinstance(chosen, dict):
        raise SystemExit(f"--freeze-artifact {path} missing a valid 'chosen' block")
    if data.get("status") != "complete":
        if _env_flag("EVAL_ALLOW_INCOMPLETE_FREEZE", False):
            print(
                f"WARNING: freeze artifact status={data.get('status')!r} (expected 'complete'); "
                "continuing only because EVAL_ALLOW_INCOMPLETE_FREEZE=1",
                flush=True,
            )
        else:
            raise SystemExit(
                f"freeze artifact status must be 'complete' (got {data.get('status')!r}); "
                "rerun sweep to completion or set EVAL_ALLOW_INCOMPLETE_FREEZE=1 for explicit override"
            )
    return data


def _pin_policy_from_freeze(
    chosen: dict[str, Any], payload: dict[str, Any]
) -> list[str]:
    """Enforce that the eval ran at the thresholds the freeze artifact chose.

    Returns a list of failure messages (empty when OK). This is the same
    contract as the env-based ``EVAL_EXPECT_POLICY_*`` check, just sourced
    from the freeze artifact so CI cannot drift from the sweep.
    """
    exp_a = chosen.get("confidence_abstain_threshold")
    exp_u = chosen.get("confidence_uncertain_threshold")
    if exp_a is None or exp_u is None:
        return [
            "freeze artifact missing confidence_abstain_threshold / confidence_uncertain_threshold"
        ]
    eff = ((payload.get("policy") or {}).get("effective")) or {}
    got_a = eff.get("confidence_abstain_threshold")
    got_u = eff.get("confidence_uncertain_threshold")
    if got_a is None or got_u is None:
        return [
            "policy.effective missing in eval result (re-run eval with current run_eval.py)"
        ]
    eps = 1e-6
    failures: list[str] = []
    if abs(float(got_a) - float(exp_a)) > eps:
        failures.append(
            f"policy.abstain mismatch with freeze artifact: expected {exp_a}, got {got_a}"
        )
    if abs(float(got_u) - float(exp_u)) > eps:
        failures.append(
            f"policy.uncertain mismatch with freeze artifact: expected {exp_u}, got {got_u}"
        )
    return failures


def _pin_policy_version_from_freeze(
    freeze: dict[str, Any], payload: dict[str, Any]
) -> list[str]:
    expected = _normalize_policy_version(freeze.get("pipeline_policy_version"))
    if not expected:
        return []
    effective = ((payload.get("policy") or {}).get("effective")) or {}
    got = _normalize_policy_version(effective.get("pipeline_policy_version_key"))
    if not got:
        got = _normalize_policy_version((payload.get("policy") or {}).get("pipeline_policy_version"))
    if not got:
        return [
            "cannot verify policy version: eval result missing policy.effective.pipeline_policy_version_key"
        ]
    if got != expected:
        return [f"policy version mismatch with freeze artifact: expected {expected}, got {got}"]
    return []


def _regression_floor(snapshot: dict[str, Any], *, slack: float) -> dict[str, float]:
    """Derive minimum acceptable metric values from the freeze snapshot.

    ``slack`` (default 0.0) allows a small drift tolerance — a release may be
    up to ``slack`` *worse* than the frozen metric before it fails. Set via
    ``--freeze-slack`` or ``EVAL_FREEZE_SLACK``.
    """
    floor: dict[str, float] = {}
    tf = snapshot.get("title_f1")
    if isinstance(tf, (int, float)):
        floor["title_f1"] = max(0.0, float(tf) - slack)
    de = snapshot.get("deadline_exact")
    if isinstance(de, (int, float)):
        floor["deadline_exact"] = max(0.0, float(de) - slack)
    # ECE is an "upper is worse" metric — flip the direction.
    ece = snapshot.get("ece")
    if isinstance(ece, (int, float)):
        floor["calibration_ece_max"] = float(ece) + slack
    return floor


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when eval quality regresses below thresholds"
    )
    parser.add_argument(
        "--result", required=True, help="Path to eval result JSON from run_eval.py"
    )
    parser.add_argument(
        "--freeze-artifact",
        type=Path,
        default=None,
        help=(
            "Optional path to sweep freeze JSON (policy_freeze/chosen_*.json); "
            "pins policy thresholds and uses the frozen metric snapshot as the "
            "regression floor"
        ),
    )
    parser.add_argument(
        "--freeze-slack",
        type=float,
        default=float(os.getenv("EVAL_FREEZE_SLACK", "0.0")),
        help="Allowed drift below frozen metric before gate fails (default 0.0)",
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.result).read_text("utf-8"))
    overall = payload.get("overall") or {}
    model_stats = payload.get("model_stats") or {}

    failed: list[str] = []

    # 1) Policy-threshold pinning (env-based OR freeze-artifact-based).
    exp_a_env = os.getenv("EVAL_EXPECT_POLICY_ABSTAIN")
    exp_u_env = os.getenv("EVAL_EXPECT_POLICY_UNCERTAIN")
    if exp_a_env and exp_u_env and str(exp_a_env).strip() and str(exp_u_env).strip():
        pol = payload.get("policy") or {}
        eff = pol.get("effective") or {}
        got_a = eff.get("confidence_abstain_threshold")
        got_u = eff.get("confidence_uncertain_threshold")
        if got_a is None or got_u is None:
            failed.append(
                "policy.effective missing (re-run eval with current run_eval.py after pipeline eval)"
            )
        else:
            ea, eu, ga, gu = float(exp_a_env), float(exp_u_env), float(got_a), float(got_u)
            eps = 1e-6
            if abs(ga - ea) > eps or abs(gu - eu) > eps:
                failed.append(
                    f"policy threshold mismatch: expected abstain={ea} uncertain={eu}, got {ga} {gu}"
                )

    # 2) Metric-level minimums, merging env defaults with freeze floor.
    title_f1 = float(((overall.get("title_f1") or {}).get("f1")) or 0.0)
    deadline_exact = float(overall.get("deadline_exact") or 0.0)
    noise_precision = float(((overall.get("title_f1") or {}).get("precision")) or 0.0)
    ece_val = float((overall.get("calibration") or {}).get("ece") or 0.0)

    min_title_f1 = _threshold("EVAL_MIN_TITLE_F1", 0.75)
    min_deadline_exact = _threshold("EVAL_MIN_DEADLINE_EXACT", 0.70)
    min_noise_precision = _threshold("EVAL_MIN_NOISE_PRECISION", 0.80)
    max_ece_env = os.getenv("EVAL_MAX_CALIBRATION_ECE")
    max_ece: float | None = float(max_ece_env) if max_ece_env and str(max_ece_env).strip() else None

    freeze_info: dict[str, Any] = {}
    if args.freeze_artifact is not None:
        freeze = _load_freeze(args.freeze_artifact)
        chosen = freeze.get("chosen") or {}
        freeze_info = {
            "path": str(args.freeze_artifact),
            "sweep_batch_utc": freeze.get("sweep_batch_utc"),
            "policy_version": freeze.get("pipeline_policy_version"),
        }

        failed.extend(_pin_policy_from_freeze(chosen, payload))
        failed.extend(_pin_policy_version_from_freeze(freeze, payload))

        snapshot = chosen.get("metrics_snapshot") or {}
        floor = _regression_floor(snapshot, slack=max(0.0, args.freeze_slack))
        if "title_f1" in floor:
            min_title_f1 = max(min_title_f1, floor["title_f1"])
        if "deadline_exact" in floor:
            min_deadline_exact = max(min_deadline_exact, floor["deadline_exact"])
        if "calibration_ece_max" in floor:
            # Freeze-derived ECE ceiling is *tighter*, so take the min of the two.
            max_ece = floor["calibration_ece_max"] if max_ece is None else min(max_ece, floor["calibration_ece_max"])

    checks = [
        ("title_f1", title_f1, min_title_f1),
        ("deadline_exact", deadline_exact, min_deadline_exact),
        ("noise_precision", noise_precision, min_noise_precision),
    ]
    for name, value, minimum in checks:
        if value < minimum:
            failed.append(f"{name}: {value:.4f} < {minimum:.4f}")

    if max_ece is not None and ece_val > max_ece:
        failed.append(f"calibration_ece: {ece_val:.4f} > {max_ece:.4f}")

    # 3) Eval-integrity checks (guard against passing with contaminated artifacts).
    allow_partial = _env_flag("EVAL_ALLOW_ABORTED_PARTIAL", False)
    aborted_early = bool(payload.get("aborted_early") or (payload.get("eval_notes") or {}).get("aborted_early"))
    if aborted_early and not allow_partial:
        failed.append(
            "eval artifact is partial (aborted_early=true); rerun after quota reset or set EVAL_ALLOW_ABORTED_PARTIAL=1"
        )

    max_runtime_errors = int(_threshold("EVAL_MAX_RUNTIME_ERRORS", 0))
    runtime_error_count = int(payload.get("runtime_error_count") or 0)
    if runtime_error_count > max_runtime_errors:
        failed.append(
            f"runtime_error_count: {runtime_error_count} > {max_runtime_errors} "
            "(artifact contaminated by runtime failures)"
        )

    require_clean_provenance = _env_flag("EVAL_REQUIRE_CLEAN_MODEL_PROVENANCE", True)
    samples_using_fallback = int(model_stats.get("samples_using_fallback") or 0)
    if require_clean_provenance and (
        bool(model_stats.get("contaminated")) or samples_using_fallback > 0
    ):
        failed.append(
            "model provenance contaminated (fallback model mixed into eval); "
            "rerun with strict primary / healthy quota or set EVAL_REQUIRE_CLEAN_MODEL_PROVENANCE=0"
        )

    print(
        f"title_f1={title_f1:.4f} deadline_exact={deadline_exact:.4f} noise_precision={noise_precision:.4f}"
    )
    abst = overall.get("abstention") or {}
    if abst:
        we = abst.get("when_expected_empty") or {}
        wn = abst.get("when_expected_nonempty") or {}
        print(
            f"abstention: correct_empty={we.get('correct_abstain_rate')} "
            f"false_answer_empty={we.get('false_answer_rate')} "
            f"false_abstain_nonempty={wn.get('false_abstain_rate')}"
        )
    cal = overall.get("calibration") or {}
    if cal.get("ece") is not None:
        print(f"calibration_ece={cal.get('ece')} confidence_pairs={cal.get('confidence_samples', 0)}")
    if freeze_info:
        print(
            f"freeze: path={freeze_info['path']} batch={freeze_info.get('sweep_batch_utc')} "
            f"policy={freeze_info.get('policy_version')}"
        )

    if failed:
        print("QUALITY GATE FAILED")
        for item in failed:
            print(f"- {item}")
        return 2

    print("QUALITY GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
