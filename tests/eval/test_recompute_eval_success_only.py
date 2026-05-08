from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from recompute_eval_success_only import recompute

ROOT = Path(__file__).resolve().parents[2]


def _scores(**kwargs):
    base = {
        "title": {"tp": 0, "fp": 0, "fn": 0},
        "assignee": {"tp": 0, "fp": 0, "fn": 0},
        "deadline": {"exact": 0, "near": 0, "total": 0},
        "conflict": {"tp": 0, "fp": 0, "fn": 0},
        "conflict_eval_skipped": False,
        "abstention": {
            "expected_empty": True,
            "correct_abstain": True,
            "false_answer_on_empty": False,
            "false_abstain_on_nonempty": False,
        },
        "calibration_bins": [{"n": 0, "correct": 0} for _ in range(5)],
    }
    base.update(kwargs)
    return base


def test_recompute_keeps_only_samples_not_in_runtime_errors():
    payload = {
        "method": "pipeline",
        "policy": {},
        "model_stats": {"strict_primary_mode": True},
        "dataset_info": {"path": "/x/dataset.json", "requested_samples": 2, "limit_applied": None},
        "eval_notes": {},
        "runtime_errors": [{"index": 0, "id": "bad", "error": "boom", "kind": "other"}],
        "sample_details": [
            {
                "id": "bad",
                "category": "c1",
                "scores": _scores(),
                "error_types": ["complete_miss"],
            },
            {
                "id": "good",
                "category": "c1",
                "scores": _scores(
                    title={"tp": 1, "fp": 0, "fn": 0},
                    abstention={
                        "expected_empty": False,
                        "correct_abstain": False,
                        "false_answer_on_empty": False,
                        "false_abstain_on_nonempty": False,
                    },
                ),
                "error_types": [],
            },
        ],
    }
    out = recompute(payload)
    assert [d["id"] for d in out["sample_details"]] == ["good"]
    assert out["runtime_error_count"] == 0
    assert out["overall"]["counts"]["samples"] == 1
    assert out["eval_notes"]["success_only_original_runtime_error_count"] == 1


def test_cli_writes_json(tmp_path: Path) -> None:
    src = tmp_path / "in.json"
    dst = tmp_path / "out.json"
    src.write_text(
        json.dumps(
            {
                "method": "pipeline",
                "policy": {},
                "model_stats": {},
                "dataset_info": {"path": "/d.json"},
                "eval_notes": {},
                "runtime_errors": [],
                "sample_details": [
                    {
                        "id": "only",
                        "category": "c",
                        "scores": _scores(),
                        "error_types": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cp = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tests" / "eval" / "recompute_eval_success_only.py"),
            "--input",
            str(src),
            "--output",
            str(dst),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "kept 1 success" in cp.stdout
    body = json.loads(dst.read_text(encoding="utf-8"))
    assert len(body["sample_details"]) == 1


def test_recompute_raises_when_scores_missing():
    payload = {
        "method": "pipeline",
        "runtime_errors": [],
        "sample_details": [{"id": "x", "category": "c"}],
    }
    with pytest.raises(SystemExit, match="missing scores"):
        recompute(payload)
