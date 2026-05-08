"""Unit tests for post-hoc confidence calibration (Q-04).

Covers the runtime loader, the two supported artifact shapes, graceful
fallback when the artifact is missing/invalid, and the end-to-end wiring
inside ``validate_tasks`` (raw vs calibrated confidence driving the policy
band, ``calibration_version`` stamping, identity when disabled).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipeline import calibration
from app.pipeline.calibration import (
    Calibrator,
    _apply_histogram,
    _apply_isotonic,
    get_runtime_calibrator,
    reset_calibrator_cache,
)


@pytest.fixture(autouse=True)
def _reset_calib_state(monkeypatch):
    monkeypatch.delenv("CALIBRATION_ARTIFACT_PATH", raising=False)
    reset_calibrator_cache()
    yield
    reset_calibrator_cache()


def _write_artifact(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "cal.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_isotonic_apply_interpolates_linearly_between_knots() -> None:
    knots = ((0.0, 0.1), (0.5, 0.4), (1.0, 0.9))
    assert _apply_isotonic(knots, 0.0) == pytest.approx(0.1)
    assert _apply_isotonic(knots, 0.5) == pytest.approx(0.4)
    assert _apply_isotonic(knots, 0.25) == pytest.approx(0.25)  # midpoint of 0.1..0.4
    assert _apply_isotonic(knots, 0.75) == pytest.approx(0.65)  # midpoint of 0.4..0.9


def test_isotonic_apply_clamps_outside_range() -> None:
    knots = ((0.2, 0.3), (0.8, 0.7))
    assert _apply_isotonic(knots, -1.0) == pytest.approx(0.3)
    assert _apply_isotonic(knots, 2.0) == pytest.approx(0.7)


def test_histogram_apply_finds_bin_and_defaults_tail() -> None:
    bins = ((0.0, 0.5, 0.2), (0.5, 1.0, 0.9))
    assert _apply_histogram(bins, 0.1) == pytest.approx(0.2)
    assert _apply_histogram(bins, 0.6) == pytest.approx(0.9)
    assert _apply_histogram(bins, 1.0) == pytest.approx(0.9)  # upper boundary uses last bin


def test_load_isotonic_artifact_round_trip(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "artifact_schema_version": 2,
        "method": "isotonic",
        "fit_time_utc": "2026-04-18T10:00:00Z",
        "git_sha": "abc123def456",
        "source_eval": "tests/eval/results/run.json",
        "source_eval_sha256": "deadbeef",
        "pairs_used": 100,
        "ece_before": 0.25,
        "ece_after": 0.05,
        "knots": [[0.0, 0.0], [0.5, 0.3], [1.0, 0.9]],
    }
    path = _write_artifact(tmp_path, payload)
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))

    cal = get_runtime_calibrator()
    assert isinstance(cal, Calibrator)
    assert cal.method == "isotonic"
    assert cal.pairs_used == 100
    assert cal.ece_before == 0.25
    assert cal.ece_after == 0.05
    assert cal.apply(0.5) == pytest.approx(0.3)
    assert "isotonic@abc123de" in cal.version_tag()


def test_load_histogram_artifact_round_trip(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "artifact_schema_version": 2,
        "method": "histogram_binning",
        "fit_time_utc": "2026-04-18T10:00:00Z",
        "pairs_used": 25,
        "bins": [
            {"lo": 0.0, "hi": 0.5, "n": 10, "empirical_accuracy": 0.2},
            {"lo": 0.5, "hi": 1.0, "n": 15, "empirical_accuracy": 0.9},
        ],
    }
    path = _write_artifact(tmp_path, payload)
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))

    cal = get_runtime_calibrator()
    assert isinstance(cal, Calibrator)
    assert cal.method == "histogram_binning"
    assert cal.apply(0.3) == pytest.approx(0.2)
    assert cal.apply(0.7) == pytest.approx(0.9)


def test_missing_env_returns_none() -> None:
    assert get_runtime_calibrator() is None


def test_missing_file_returns_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(tmp_path / "nope.json"))
    assert get_runtime_calibrator() is None


def test_unsupported_method_returns_none(monkeypatch, tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, {"method": "temperature_scaling", "temperature": 1.2})
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))
    assert get_runtime_calibrator() is None


def test_malformed_json_returns_none(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "cal.json"
    p.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(p))
    assert get_runtime_calibrator() is None


def test_isotonic_without_knots_falls_back_to_none(monkeypatch, tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, {"method": "isotonic", "knots": []})
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))
    assert get_runtime_calibrator() is None


def test_histogram_without_bins_falls_back_to_none(monkeypatch, tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, {"method": "histogram_binning", "bins": []})
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))
    assert get_runtime_calibrator() is None


def test_validate_tasks_applies_calibration_before_policy(monkeypatch, tmp_path: Path) -> None:
    """End-to-end: a raw confidence 0.9 that the calibrator shrinks to 0.5
    should push the task into the abstain band (abstain=0.6, uncertain=0.8)."""
    payload = {
        "artifact_schema_version": 2,
        "method": "isotonic",
        "fit_time_utc": "2026-04-18T10:00:00Z",
        "git_sha": "deadbeef12345",
        "pairs_used": 50,
        "knots": [[0.0, 0.0], [0.9, 0.5], [1.0, 0.5]],
    }
    path = _write_artifact(tmp_path, payload)
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))
    reset_calibrator_cache()

    from app.pipeline.nodes.validate_tasks import validate_tasks

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Ann",
                    "deadline": "2026-04-20",
                    "confidence": 0.9,
                }
            ],
            "errors": [],
            "existing_tasks": [],
        }
    )
    task = result["validated_tasks"][0]
    assert task["raw_confidence"] == pytest.approx(0.9)
    assert task["confidence"] == pytest.approx(0.5)
    assert task["decision_band"] == "abstain"
    assert task["abstained"] is True
    assert task["calibration_method"] == "isotonic"
    assert "isotonic@deadbeef" in task["calibration_version"]


def test_validate_tasks_identity_when_artifact_absent(monkeypatch) -> None:
    monkeypatch.delenv("CALIBRATION_ARTIFACT_PATH", raising=False)
    reset_calibrator_cache()

    from app.pipeline.nodes.validate_tasks import validate_tasks

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Ann",
                    "deadline": "2026-04-20",
                    "confidence": 0.9,
                }
            ],
            "errors": [],
            "existing_tasks": [],
        }
    )
    task = result["validated_tasks"][0]
    assert task["confidence"] == pytest.approx(0.9)
    assert task["raw_confidence"] == pytest.approx(0.9)
    assert "calibration_version" not in task
    assert task["decision_band"] == "accept"


def test_validate_tasks_preserves_none_confidence(monkeypatch, tmp_path: Path) -> None:
    """A missing LLM confidence must stay abstain — calibration cannot rescue it."""
    payload = {
        "artifact_schema_version": 2,
        "method": "isotonic",
        "pairs_used": 10,
        "knots": [[0.0, 0.95], [1.0, 0.95]],
    }
    path = _write_artifact(tmp_path, payload)
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(path))
    reset_calibrator_cache()

    from app.pipeline.nodes.validate_tasks import validate_tasks

    result = validate_tasks(
        {
            "normalized_tasks": [
                {"title": "X", "assignee": "Ann", "deadline": "2026-04-20"},
            ],
            "errors": [],
            "existing_tasks": [],
        }
    )
    task = result["validated_tasks"][0]
    assert task["confidence"] is None
    assert task["raw_confidence"] is None
    assert task["abstained"] is True


def test_calibrator_cache_is_per_path(monkeypatch, tmp_path: Path) -> None:
    """Switching artifact paths must pick up the new file without a process
    restart. Prior implementations cached once per module load."""
    pa = _write_artifact(tmp_path / "a.json" if False else tmp_path, {"method": "isotonic", "knots": [[0.0, 0.1], [1.0, 0.1]]})
    pb_path = tmp_path / "b.json"
    pb_path.write_text(json.dumps({"method": "isotonic", "knots": [[0.0, 0.9], [1.0, 0.9]]}), encoding="utf-8")

    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(pa))
    ca = get_runtime_calibrator()
    assert ca is not None and ca.apply(0.5) == pytest.approx(0.1)

    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(pb_path))
    cb = get_runtime_calibrator()
    assert cb is not None and cb.apply(0.5) == pytest.approx(0.9)
