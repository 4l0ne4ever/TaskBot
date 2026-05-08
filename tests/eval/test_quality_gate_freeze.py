"""Tests for the freeze-artifact path in quality_gate.py (Q-07).

Verifies that the gate:
  1. Pins policy thresholds to the frozen values (fails on mismatch).
  2. Uses the frozen metric snapshot as a regression floor, merged with
     env-based minima (tighter wins).
  3. Does not regress when the live eval equals the frozen snapshot.
  4. Respects ``--freeze-slack`` so a small drift is tolerated on purpose.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_GATE = Path(__file__).resolve().parent / "quality_gate.py"


def _write_result(path: Path, *, abstain: float, uncertain: float, title_f1: float, deadline_exact: float = 0.9, ece: float = 0.1) -> None:
    payload = {
        "overall": {
            "title_f1": {"precision": 0.95, "recall": 0.9, "f1": title_f1},
            "deadline_exact": deadline_exact,
            "calibration": {"ece": ece},
            "abstention": {
                "when_expected_empty": {"correct_abstain_rate": 1.0, "false_answer_rate": 0.0},
                "when_expected_nonempty": {"false_abstain_rate": 0.0},
            },
        },
        "policy": {
            "pipeline_policy_version": "v2",
            "effective": {
                "pipeline_policy_version_key": "v2",
                "confidence_abstain_threshold": abstain,
                "confidence_uncertain_threshold": uncertain,
            }
        },
        "aborted_early": False,
        "runtime_error_count": 0,
        "model_stats": {"contaminated": False, "samples_using_fallback": 0},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_freeze(path: Path, *, abstain: float, uncertain: float, title_f1: float, deadline_exact: float = 0.9, ece: float = 0.1, status: str = "complete") -> None:
    freeze = {
        "status": status,
        "sweep_batch_utc": "20260418T100000Z",
        "pipeline_policy_version": "v2",
        "chosen": {
            "confidence_abstain_threshold": abstain,
            "confidence_uncertain_threshold": uncertain,
            "metrics_snapshot": {
                "title_f1": title_f1,
                "deadline_exact": deadline_exact,
                "ece": ece,
            },
        },
    }
    path.write_text(json.dumps(freeze), encoding="utf-8")


def _run_gate(result_path: Path, freeze_path: Path | None = None, slack: float | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_GATE), "--result", str(result_path)]
    if freeze_path is not None:
        cmd.extend(["--freeze-artifact", str(freeze_path)])
    if slack is not None:
        cmd.extend(["--freeze-slack", str(slack)])
    run_env = {"PATH": sys.executable}
    if env:
        run_env.update(env)
    import os as _os
    full_env = _os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=full_env)


def test_freeze_passes_when_eval_matches_snapshot(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.9, deadline_exact=0.85)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.9, deadline_exact=0.85)

    cp = _run_gate(result, freeze_path=freeze, env={"EVAL_MIN_TITLE_F1": "0.0", "EVAL_MIN_DEADLINE_EXACT": "0.0", "EVAL_MIN_NOISE_PRECISION": "0.0"})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "QUALITY GATE PASSED" in cp.stdout


def test_freeze_fails_when_policy_threshold_drift(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.55, uncertain=0.76, title_f1=0.95)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.9)

    cp = _run_gate(result, freeze_path=freeze, env={"EVAL_MIN_TITLE_F1": "0.0", "EVAL_MIN_DEADLINE_EXACT": "0.0", "EVAL_MIN_NOISE_PRECISION": "0.0"})
    assert cp.returncode == 2, cp.stdout
    assert "policy.abstain mismatch" in cp.stdout or "policy.uncertain mismatch" in cp.stdout


def test_freeze_metric_regression_fails(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.70)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.90)

    cp = _run_gate(result, freeze_path=freeze, env={"EVAL_MIN_TITLE_F1": "0.0", "EVAL_MIN_DEADLINE_EXACT": "0.0", "EVAL_MIN_NOISE_PRECISION": "0.0"})
    assert cp.returncode == 2, cp.stdout
    assert "title_f1" in cp.stdout


def test_freeze_slack_tolerates_small_drift(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.88)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.90)

    cp = _run_gate(
        result, freeze_path=freeze, slack=0.05,
        env={"EVAL_MIN_TITLE_F1": "0.0", "EVAL_MIN_DEADLINE_EXACT": "0.0", "EVAL_MIN_NOISE_PRECISION": "0.0"}
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_freeze_ece_ceiling_is_tighter_of_env_and_freeze(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.9, ece=0.15)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.9, ece=0.10)

    cp = _run_gate(
        result, freeze_path=freeze,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
            "EVAL_MAX_CALIBRATION_ECE": "0.20",
        },
    )
    assert cp.returncode == 2, cp.stdout
    assert "calibration_ece" in cp.stdout


def test_gate_still_works_without_freeze(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95, deadline_exact=0.85)
    cp = _run_gate(result, env={"EVAL_MIN_TITLE_F1": "0.8", "EVAL_MIN_DEADLINE_EXACT": "0.8", "EVAL_MIN_NOISE_PRECISION": "0.8"})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "QUALITY GATE PASSED" in cp.stdout


def test_freeze_incomplete_status_fails_by_default(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    _write_freeze(
        freeze, abstain=0.6, uncertain=0.8, title_f1=0.9, status="partial"
    )
    cp = _run_gate(
        result,
        freeze_path=freeze,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
        },
    )
    assert cp.returncode != 0
    assert "status must be 'complete'" in (cp.stdout + cp.stderr)


def test_freeze_incomplete_status_can_be_overridden(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    _write_freeze(
        freeze, abstain=0.6, uncertain=0.8, title_f1=0.9, status="partial"
    )
    cp = _run_gate(
        result,
        freeze_path=freeze,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
            "EVAL_ALLOW_INCOMPLETE_FREEZE": "1",
        },
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_freeze_fails_when_policy_version_drift(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    freeze = tmp_path / "chosen.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    _write_freeze(freeze, abstain=0.6, uncertain=0.8, title_f1=0.9)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["policy"]["effective"]["pipeline_policy_version_key"] = "v1"
    result.write_text(json.dumps(payload), encoding="utf-8")

    cp = _run_gate(
        result,
        freeze_path=freeze,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
        },
    )
    assert cp.returncode == 2, cp.stdout
    assert "policy version mismatch" in cp.stdout


def test_gate_fails_for_partial_eval_artifact_by_default(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["aborted_early"] = True
    result.write_text(json.dumps(payload), encoding="utf-8")
    cp = _run_gate(
        result,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
        },
    )
    assert cp.returncode == 2, cp.stdout
    assert "aborted_early" in cp.stdout


def test_gate_allows_partial_eval_when_explicit_override(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["aborted_early"] = True
    result.write_text(json.dumps(payload), encoding="utf-8")
    cp = _run_gate(
        result,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
            "EVAL_ALLOW_ABORTED_PARTIAL": "1",
        },
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_gate_fails_when_runtime_errors_exceed_budget(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["runtime_error_count"] = 2
    result.write_text(json.dumps(payload), encoding="utf-8")
    cp = _run_gate(
        result,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
            "EVAL_MAX_RUNTIME_ERRORS": "0",
        },
    )
    assert cp.returncode == 2, cp.stdout
    assert "runtime_error_count" in cp.stdout


def test_gate_fails_when_model_provenance_contaminated(tmp_path: Path) -> None:
    result = tmp_path / "eval.json"
    _write_result(result, abstain=0.6, uncertain=0.8, title_f1=0.95)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["model_stats"]["contaminated"] = True
    payload["model_stats"]["samples_using_fallback"] = 3
    result.write_text(json.dumps(payload), encoding="utf-8")
    cp = _run_gate(
        result,
        env={
            "EVAL_MIN_TITLE_F1": "0.0",
            "EVAL_MIN_DEADLINE_EXACT": "0.0",
            "EVAL_MIN_NOISE_PRECISION": "0.0",
        },
    )
    assert cp.returncode == 2, cp.stdout
    assert "model provenance contaminated" in cp.stdout
