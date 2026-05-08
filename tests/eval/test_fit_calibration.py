"""Tests for the calibration artifact fitting pipeline (Q-04)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(_EVAL))

from fit_verbalized_calibration import (  # noqa: E402
    ARTIFACT_SCHEMA_VERSION,
    _apply_histogram,
    _apply_isotonic,
    _ece_from_points,
    fit_histogram,
    fit_isotonic,
)


def test_fit_histogram_monotonic_bins():
    pts = [(0.1, True), (0.1, False), (0.9, True), (0.9, True), (0.5, False)]
    out = fit_histogram(pts, n_bins=5)
    assert out["pairs_used"] == 5
    assert out["method"] == "histogram_binning"
    assert len(out["bins"]) == 5


def test_histogram_empty_bins_use_laplace_prior():
    out = fit_histogram([(0.9, True)], n_bins=5)
    empty = [b for b in out["bins"] if b["n"] == 0]
    assert empty, "expected empty bins for sparse input"
    for b in empty:
        assert b["empirical_accuracy"] == pytest.approx(0.5)


def test_fit_isotonic_is_monotonic_non_decreasing():
    pts = [(0.1, False), (0.3, False), (0.5, True), (0.7, True), (0.9, True)]
    out = fit_isotonic(pts)
    assert out["method"] == "isotonic"
    knots = out["knots"]
    ys = [y for _, y in knots]
    for i in range(1, len(ys)):
        assert ys[i] >= ys[i - 1], f"PAV output not monotone at idx {i}: {ys}"


def test_pav_pools_adjacent_violators():
    """When consecutive pairs violate monotonicity they must be averaged so
    the resulting step function is non-decreasing."""
    # Two points at same x but opposite outcomes → pooled at 0.5.
    pts = [(0.3, True), (0.3, False), (0.9, True)]
    out = fit_isotonic(pts)
    y_at_0_3 = _apply_isotonic(tuple(tuple(k) for k in out["knots"]), 0.3)
    assert y_at_0_3 == pytest.approx(0.5)
    ys = [y for _, y in out["knots"]]
    for i in range(1, len(ys)):
        assert ys[i] >= ys[i - 1]


def test_pav_aggregates_tied_x_before_pooling():
    """Regression test: LLM verbalized confidence tends to cluster at 0.8 /
    0.9 / 0.95. Without pre-aggregation the knots would depend on insertion
    order (and could sit anywhere between 0 and 1); after aggregation the
    calibrated value for the tied-``x`` bucket must equal its empirical
    accuracy.
    """
    pts = [(0.92, True)] * 26 + [(0.92, False)] * 24  # 52% correct
    out = fit_isotonic(pts)
    y = _apply_isotonic(tuple(tuple(k) for k in out["knots"]), 0.92)
    assert y == pytest.approx(26 / 50, abs=1e-6)


def test_apply_isotonic_linear_interpolation():
    knots = ((0.0, 0.0), (1.0, 1.0))
    assert _apply_isotonic(knots, 0.5) == pytest.approx(0.5)
    assert _apply_isotonic(knots, 0.25) == pytest.approx(0.25)


def test_ece_from_points_matches_manual_calculation():
    # Perfectly miscalibrated: raw=0.9 but actual accuracy=0 → ECE=0.9
    pts = [(0.9, 0.0)] * 10
    assert _ece_from_points(pts) == pytest.approx(0.9)


def test_cli_emits_schema_versioned_artifact(tmp_path: Path):
    """End-to-end CLI: given a minimal eval JSON, the CLI writes an artifact
    with schema_version, method, pairs_used, knots/bins, ece_before/after."""
    eval_payload = {
        "sample_details": [
            {
                "expected_tasks": [{"title": "Submit report"}],
                "predicted_tasks": [{"title": "Submit report", "confidence": 0.9}],
            },
            {
                "expected_tasks": [{"title": "Prepare slides"}],
                "predicted_tasks": [{"title": "Prepare slides", "confidence": 0.4}],
            },
            {
                "expected_tasks": [{"title": "Call Bob"}],
                "predicted_tasks": [{"title": "Totally different", "confidence": 0.95}],
            },
        ]
    }
    eval_path = tmp_path / "eval.json"
    eval_path.write_text(json.dumps(eval_payload), encoding="utf-8")
    out_path = tmp_path / "cal.json"

    subprocess.run(
        [
            sys.executable,
            str(_EVAL / "fit_verbalized_calibration.py"),
            str(eval_path),
            "--out",
            str(out_path),
            "--method",
            "histogram",
            "--bins",
            "5",
        ],
        check=True,
    )

    artifact = json.loads(out_path.read_text(encoding="utf-8"))
    assert artifact["artifact_schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert artifact["method"] == "histogram_binning"
    assert artifact["pairs_used"] >= 2  # the matched pairs
    assert "bins" in artifact
    assert "fit_time_utc" in artifact
    assert "ece_before" in artifact
    assert "ece_after" in artifact
    assert artifact["source_eval_sha256"]


def test_auto_selects_histogram_on_tiny_sample(tmp_path: Path):
    eval_payload = {
        "sample_details": [
            {
                "expected_tasks": [{"title": "X"}],
                "predicted_tasks": [{"title": "X", "confidence": 0.7}],
            }
        ]
    }
    eval_path = tmp_path / "eval.json"
    eval_path.write_text(json.dumps(eval_payload), encoding="utf-8")
    out_path = tmp_path / "cal.json"

    subprocess.run(
        [
            sys.executable,
            str(_EVAL / "fit_verbalized_calibration.py"),
            str(eval_path),
            "--out",
            str(out_path),
            "--method",
            "auto",
        ],
        check=True,
    )
    artifact = json.loads(out_path.read_text(encoding="utf-8"))
    assert artifact["method"] == "histogram_binning"
    assert artifact["method_auto_selected"] is True
