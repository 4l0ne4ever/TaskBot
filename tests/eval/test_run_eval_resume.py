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


def test_resume_skips_cached_ids_and_keeps_order(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    prior = tmp_path / "prior.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")

    calls: list[str] = []

    def _fake_pipeline(sample: dict) -> dict:
        calls.append(str(sample.get("id")))
        return {"tasks": [], "conflicts": [], "missing_fields": [], "_meta": {"model_provenance": {}}}

    prior_payload = {
        "sample_details": [
            {
                "id": "a",
                "category": "email_simple",
                "language": "en",
                "edge_tags": [],
                "input_excerpt": "",
                "expected_task_count": 1,
                "expected_tasks": [],
                "predicted_tasks": [],
                "scores": {
                    "title": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "assignee": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "deadline": {"exact": 0, "near": 0, "total": 0},
                    "conflict": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "abstention": {},
                    "calibration_bins": {},
                },
                "error_types": [],
                "is_correct": True,
            }
        ],
        "eval_notes": {"eval_run_id": "rid-resume-test", "langsmith_session_name": "sess-resume"},
        "dataset_info": {"path": str(dataset)},
        "runtime_errors": [],
    }
    prior.write_text(json.dumps(prior_payload), encoding="utf-8")

    monkeypatch.setitem(run_eval.METHODS, "pipeline", _fake_pipeline)
    monkeypatch.setenv("EVAL_ABORT_EXIT_ZERO", "1")
    monkeypatch.delenv("EVAL_RUN_ID", raising=False)
    monkeypatch.delenv("LANGSMITH_SESSION_NAME", raising=False)
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
            str(out),
            "--resume",
            str(prior),
        ],
    )

    assert run_eval.main() == 0
    assert calls == ["b"], "only uncached sample should invoke pipeline"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [d["id"] for d in payload["sample_details"]] == ["a", "b"]
    assert payload["eval_notes"]["eval_run_id"] == "rid-resume-test"


def test_implicit_resume_same_output_without_resume_flag(monkeypatch, tmp_path):
    """Re-run with the same --output path merges partial JSON (no --resume needed)."""
    dataset = tmp_path / "dataset.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")
    cur_ds = str(dataset.resolve())

    detail_a = {
        "id": "a",
        "category": "email_simple",
        "language": "en",
        "edge_tags": [],
        "input_excerpt": "",
        "expected_task_count": 1,
        "expected_tasks": [],
        "predicted_tasks": [],
        "scores": {
            "title": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "assignee": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "deadline": {"exact": 0, "near": 0, "total": 0},
            "conflict": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "abstention": {},
            "calibration_bins": {},
        },
        "error_types": [],
        "is_correct": True,
    }
    partial = {
        "method": "pipeline",
        "aborted_early": True,
        "sample_details": [detail_a],
        "dataset_info": {"path": cur_ds, "requested_samples": 2},
        "eval_notes": {"eval_run_id": "rid-implicit", "langsmith_session_name": "sess-implicit"},
        "runtime_errors": [],
        "policy": {"policy_threshold_overrides": {}},
    }
    out.write_text(json.dumps(partial), encoding="utf-8")

    calls: list[str] = []

    def _fake_pipeline(sample: dict) -> dict:
        calls.append(str(sample.get("id")))
        return {"tasks": [], "conflicts": [], "missing_fields": [], "_meta": {"model_provenance": {}}}

    monkeypatch.setitem(run_eval.METHODS, "pipeline", _fake_pipeline)
    monkeypatch.setenv("EVAL_ABORT_EXIT_ZERO", "1")
    monkeypatch.delenv("EVAL_RUN_ID", raising=False)
    monkeypatch.delenv("LANGSMITH_SESSION_NAME", raising=False)
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
            str(out),
        ],
    )

    assert run_eval.main() == 0
    assert calls == ["b"]
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [d["id"] for d in payload["sample_details"]] == ["a", "b"]


def test_implicit_resume_errors_when_env_thresholds_differ_from_artifact(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")
    cur_ds = str(dataset.resolve())
    partial = {
        "method": "pipeline",
        "sample_details": [
            {
                "id": "a",
                "category": "email_simple",
                "language": "en",
                "edge_tags": [],
                "input_excerpt": "",
                "expected_task_count": 1,
                "expected_tasks": [],
                "predicted_tasks": [],
                "scores": {
                    "title": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "assignee": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "deadline": {"exact": 0, "near": 0, "total": 0},
                    "conflict": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "abstention": {},
                    "calibration_bins": {},
                },
                "error_types": [],
                "is_correct": True,
            }
        ],
        "dataset_info": {"path": cur_ds},
        "eval_notes": {},
        "runtime_errors": [],
        "policy": {"policy_threshold_overrides": {"abstain": "0.55", "uncertain": "0.76"}},
    }
    out.write_text(json.dumps(partial), encoding="utf-8")
    monkeypatch.setenv("PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE", "0.6")
    monkeypatch.setenv("PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE", "0.76")
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
            str(out),
        ],
    )
    assert run_eval.main() == 2


def _one_pipeline_detail(sid: str) -> dict:
    return {
        "id": sid,
        "category": "email_simple",
        "language": "en",
        "edge_tags": [],
        "input_excerpt": "",
        "expected_task_count": 1,
        "expected_tasks": [],
        "predicted_tasks": [],
        "scores": {
            "title": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "assignee": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "deadline": {"exact": 0, "near": 0, "total": 0},
            "conflict": {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "abstention": {},
            "calibration_bins": {},
        },
        "error_types": [],
        "is_correct": True,
    }


def test_implicit_resume_errors_when_dataset_path_missing(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")
    partial = {
        "method": "pipeline",
        "sample_details": [_one_pipeline_detail("a")],
        "dataset_info": {"requested_samples": 2},
        "eval_notes": {},
        "runtime_errors": [],
        "policy": {"policy_threshold_overrides": {}},
    }
    out.write_text(json.dumps(partial), encoding="utf-8")
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
            str(out),
        ],
    )
    assert run_eval.main() == 2


def test_implicit_resume_errors_when_dataset_path_mismatches(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    other = tmp_path / "other.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")
    other.write_text("[]", encoding="utf-8")
    partial = {
        "method": "pipeline",
        "sample_details": [_one_pipeline_detail("a")],
        "dataset_info": {"path": str(other.resolve()), "requested_samples": 2},
        "eval_notes": {},
        "runtime_errors": [],
        "policy": {"policy_threshold_overrides": {}},
    }
    out.write_text(json.dumps(partial), encoding="utf-8")
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
            str(out),
        ],
    )
    assert run_eval.main() == 2


def test_implicit_resume_errors_when_limit_applied_mismatches(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset.json"
    out = tmp_path / "out.json"
    dataset.write_text(json.dumps([_sample("a"), _sample("b")]), encoding="utf-8")
    cur_ds = str(dataset.resolve())
    partial = {
        "method": "pipeline",
        "sample_details": [_one_pipeline_detail("a")],
        "dataset_info": {"path": cur_ds, "requested_samples": 2, "limit_applied": 99},
        "eval_notes": {},
        "runtime_errors": [],
        "policy": {"policy_threshold_overrides": {}},
    }
    out.write_text(json.dumps(partial), encoding="utf-8")
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
            str(out),
            "--limit",
            "2",
        ],
    )
    assert run_eval.main() == 2
