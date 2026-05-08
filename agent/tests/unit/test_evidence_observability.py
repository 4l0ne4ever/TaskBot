"""Verify that evidence-quote and calibration telemetry reach the obs row (Q-02/Q-04).

The validation node emits ``evidence_stats`` + ``calibration_info`` into the
observability pipeline_run_trace record. These keys are what the Redis
dashboard / LangSmith reads to measure hallucination guardrail coverage and
whether the runtime calibrator was actually used on a given run.
"""
from __future__ import annotations

from unittest.mock import patch

from app.pipeline.calibration import reset_calibrator_cache
from app.pipeline.nodes.validate_tasks import validate_tasks


def test_evidence_quote_stats_recorded_in_trace(monkeypatch) -> None:
    monkeypatch.delenv("CALIBRATION_ARTIFACT_PATH", raising=False)
    reset_calibrator_cache()

    captured: dict[str, object] = {}

    def fake_record(state, tasks, policy_version, **kwargs):
        captured["kwargs"] = kwargs
        captured["tasks"] = tasks

    with patch("app.pipeline.nodes.validate_tasks.record_pipeline_run_trace", side_effect=fake_record):
        validate_tasks(
            {
                "cleaned_text": "Please submit the Q1 report by Friday.",
                "normalized_tasks": [
                    {
                        "title": "Submit Q1 report",
                        "assignee": "Ann",
                        "deadline": "2026-04-20",
                        "confidence": 0.9,
                        "evidence_quote": "submit the Q1 report",
                    },
                    {
                        "title": "Prepare slides",
                        "assignee": "Bob",
                        "deadline": "2026-04-25",
                        "confidence": 0.9,
                        "evidence_quote": "NOT IN SOURCE TEXT",
                    },
                    {
                        "title": "Call Carol",
                        "assignee": "Carol",
                        "deadline": "2026-04-22",
                        "confidence": 0.9,
                    },
                ],
                "errors": [],
                "existing_tasks": [],
            }
        )

    kwargs = captured.get("kwargs") or {}
    ev = kwargs.get("evidence_stats") or {}
    cal = kwargs.get("calibration_info") or {}
    assert ev["tasks_with_quote"] == 2
    assert ev["invalid_quote_drops"] == 1
    assert cal["applied"] is False
    assert cal["method"] is None

    # The task with invalid quote must be abstained.
    titles_abstained = {t["title"] for t in captured["tasks"] if t.get("abstained")}
    assert "Prepare slides" in titles_abstained


def test_calibration_applied_flag_set_when_artifact_loaded(monkeypatch, tmp_path) -> None:
    import json as _json

    payload = {
        "artifact_schema_version": 2,
        "method": "isotonic",
        "fit_time_utc": "2026-04-18T10:00:00Z",
        "git_sha": "deadbeef00",
        "pairs_used": 50,
        "knots": [[0.0, 0.1], [1.0, 0.9]],
    }
    p = tmp_path / "cal.json"
    p.write_text(_json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("CALIBRATION_ARTIFACT_PATH", str(p))
    reset_calibrator_cache()

    captured: dict[str, object] = {}

    def fake_record(state, tasks, policy_version, **kwargs):
        captured["kwargs"] = kwargs

    with patch("app.pipeline.nodes.validate_tasks.record_pipeline_run_trace", side_effect=fake_record):
        validate_tasks(
            {
                "normalized_tasks": [
                    {"title": "X", "assignee": "Ann", "deadline": "2026-04-20", "confidence": 0.9}
                ],
                "errors": [],
                "existing_tasks": [],
            }
        )

    cal = (captured.get("kwargs") or {}).get("calibration_info") or {}
    assert cal["applied"] is True
    assert cal["method"] == "isotonic"
    assert cal["remapped_count"] == 1
    assert isinstance(cal["version"], str) and "isotonic@" in cal["version"]
