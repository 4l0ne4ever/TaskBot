from __future__ import annotations

import json
import sys

import run_eval


def _sample(sample_id: str) -> dict:
    return {
        "id": sample_id,
        "category": "email_simple",
        "source_type": "gmail",
        "input_text": "Please send the report by Friday. An is responsible.",
        "metadata": {"sent_at": "2026-04-20"},
        "expected": {
            "tasks": [
                {
                    "title": "Send the report",
                    "assignee": "An",
                    "deadline": "2026-04-24",
                }
            ],
            "conflicts": [],
        },
    }


def test_pipeline_eval_aborts_early_on_daily_quota(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    output = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")

    def _raise_daily_quota(_sample: dict) -> dict:
        raise RuntimeError("429 rate limit reached on tokens per day (TPD)")

    monkeypatch.setitem(run_eval.METHODS, "pipeline", _raise_daily_quota)
    monkeypatch.delenv("EVAL_ABORT_EXIT_ZERO", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_eval.py",
            "--method",
            "pipeline",
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
    )

    assert run_eval.main() == 3
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["aborted_early"] is True
    assert payload["abort_reason"] == "daily_quota"
    assert payload["dataset_info"]["total_samples"] == 1
    assert payload["dataset_info"]["requested_samples"] == 2
    assert payload["runtime_error_kinds"] == {"daily_quota": 1}


def test_pipeline_eval_aborts_early_on_organization_restricted(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    output = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")

    def _raise_restricted(_sample: dict) -> dict:
        raise RuntimeError(
            "BadRequestError(\"Error code: 400 - {'error': {'message': 'Organization has been restricted.'}}\")"
        )

    monkeypatch.setitem(run_eval.METHODS, "pipeline", _raise_restricted)
    monkeypatch.delenv("EVAL_ABORT_EXIT_ZERO", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_eval.py",
            "--method",
            "pipeline",
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
    )

    assert run_eval.main() == 3
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["aborted_early"] is True
    assert payload["abort_reason"] == "organization_restricted"
    assert payload["dataset_info"]["total_samples"] == 1
    assert payload["runtime_error_kinds"] == {"organization_restricted": 1}


def test_sweep_child_can_request_zero_exit_for_parseable_partial(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    output = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")

    def _raise_daily_quota(_sample: dict) -> dict:
        raise RuntimeError("429 rate limit reached on tokens per day (TPD)")

    monkeypatch.setitem(run_eval.METHODS, "pipeline", _raise_daily_quota)
    monkeypatch.setenv("EVAL_ABORT_EXIT_ZERO", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_eval.py",
            "--method",
            "pipeline",
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
    )

    assert run_eval.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["aborted_early"] is True
    assert payload["abort_after_samples"] == 1
