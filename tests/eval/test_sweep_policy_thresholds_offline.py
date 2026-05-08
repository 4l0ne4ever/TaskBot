from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_offline_sweep_uses_candidates_without_llm(tmp_path: Path) -> None:
    result = {
        "method": "pipeline",
        "policy": {"pipeline_policy_version": "v3"},
        "model_stats": {"contaminated": False},
        "runtime_error_count": 0,
        "sample_details": [
            {
                "id": "a",
                "category": "email_simple",
                "expected_tasks": [{"title": "Submit report", "assignee": None, "deadline": None}],
                "expected_conflicts": [],
                "predicted_conflicts": [],
                "prediction_meta": {
                    "candidate_tasks": [
                        {"title": "Submit report", "confidence": 0.57, "decision_score": 0.57}
                    ]
                },
                "error_types": [],
            },
            {
                "id": "b",
                "category": "email_no_task",
                "expected_tasks": [],
                "expected_conflicts": [],
                "predicted_conflicts": [],
                "prediction_meta": {
                    "candidate_tasks": [
                        {"title": "Invented task", "confidence": 0.57, "decision_score": 0.57}
                    ]
                },
                "error_types": [],
            },
        ],
    }
    src = tmp_path / "eval.json"
    out = tmp_path / "offline.csv"
    freeze = tmp_path / "chosen.json"
    aligned = tmp_path / "aligned.json"
    src.write_text(json.dumps(result), encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "sweep_policy_thresholds_offline.py"),
        "--result",
        str(src),
        "--output",
        str(out),
        "--abstain",
        "0.55,0.60",
        "--uncertain",
        "0.80",
        "--write-freeze",
        str(freeze),
        "--write-aligned-result",
        str(aligned),
    ]
    completed = subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)

    assert "Wrote 2 offline rows" in completed.stdout
    assert "Wrote offline aligned eval result" in completed.stdout
    assert "Wrote offline aligned report" in completed.stdout
    csv_text = out.read_text(encoding="utf-8")
    assert "0.55" in csv_text
    assert "0.6" in csv_text
    payload = json.loads(freeze.read_text(encoding="utf-8"))
    assert payload["sweep_mode"] == "offline"
    assert payload["chosen"]["confidence_abstain_threshold"] == 0.6
    aligned_payload = json.loads(aligned.read_text(encoding="utf-8"))
    assert aligned_payload["policy"]["effective"]["confidence_abstain_threshold"] == 0.6
    assert aligned_payload["overall"]["title_f1"]["f1"] == 0
    assert aligned_payload["overall"]["abstention"]["when_expected_empty"]["correct_abstain_rate"] == 1.0
    assert aligned.with_name("aligned_report.md").is_file()


def test_offline_sweep_exclude_runtime_errors_drops_ids_from_metrics(tmp_path: Path) -> None:
    result = {
        "method": "pipeline",
        "policy": {"pipeline_policy_version": "v3"},
        "model_stats": {"contaminated": False},
        "runtime_error_count": 1,
        "runtime_errors": [{"index": 1, "id": "b", "error": "boom", "kind": "other"}],
        "sample_details": [
            {
                "id": "a",
                "category": "email_simple",
                "expected_tasks": [{"title": "Submit report", "assignee": None, "deadline": None}],
                "expected_conflicts": [],
                "predicted_conflicts": [],
                "prediction_meta": {
                    "candidate_tasks": [
                        {"title": "Submit report", "confidence": 0.57, "decision_score": 0.57}
                    ]
                },
                "error_types": [],
            },
            {
                "id": "b",
                "category": "email_no_task",
                "expected_tasks": [],
                "expected_conflicts": [],
                "predicted_conflicts": [],
                "prediction_meta": {
                    "candidate_tasks": [
                        {"title": "Noise", "confidence": 0.57, "decision_score": 0.57}
                    ]
                },
                "error_types": ["complete_miss"],
            },
        ],
    }
    src = tmp_path / "eval.json"
    out = tmp_path / "offline.csv"
    src.write_text(json.dumps(result), encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "sweep_policy_thresholds_offline.py"),
        "--result",
        str(src),
        "--output",
        str(out),
        "--abstain",
        "0.55",
        "--uncertain",
        "0.80",
        "--exclude-runtime-errors",
    ]
    completed = subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)
    assert "Wrote 1 offline rows" in completed.stdout

    with out.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert int(row["samples_excluded_runtime"]) == 1
    assert int(row["samples_completed"]) == 1
