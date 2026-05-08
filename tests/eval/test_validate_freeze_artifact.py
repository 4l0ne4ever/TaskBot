from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parent / "validate_freeze_artifact.py"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["abstain", "uncertain", "contaminated"], extrasaction="ignore"
        )
        w.writeheader()
        w.writerows(rows)


def _write_freeze(path: Path, *, csv_path: Path, checkpoint_path: Path, status: str = "complete") -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "pipeline_policy_version": "v2",
                "chosen": {
                    "confidence_abstain_threshold": 0.6,
                    "confidence_uncertain_threshold": 0.8,
                },
                "csv_path": str(csv_path),
                "checkpoint_path": str(checkpoint_path),
            }
        ),
        encoding="utf-8",
    )


def _write_checkpoint(path: Path, *, status: str = "complete") -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "completed_pairs": [["0.6", "0.8"]],
            }
        ),
        encoding="utf-8",
    )


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_validate_freeze_passes_for_clean_artifacts(tmp_path: Path) -> None:
    csv_path = tmp_path / "sweep.csv"
    checkpoint = tmp_path / "checkpoint.json"
    freeze = tmp_path / "chosen.json"
    _write_csv(csv_path, [{"abstain": "0.6", "uncertain": "0.8", "contaminated": "false"}])
    _write_checkpoint(checkpoint, status="complete")
    _write_freeze(freeze, csv_path=csv_path, checkpoint_path=checkpoint)
    cp = _run(["--freeze-artifact", str(freeze)])
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "FREEZE VALIDATION PASSED" in cp.stdout


def test_validate_freeze_fails_for_contaminated_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "sweep.csv"
    checkpoint = tmp_path / "checkpoint.json"
    freeze = tmp_path / "chosen.json"
    _write_csv(csv_path, [{"abstain": "0.6", "uncertain": "0.8", "contaminated": "true"}])
    _write_checkpoint(checkpoint, status="complete")
    _write_freeze(freeze, csv_path=csv_path, checkpoint_path=checkpoint)
    cp = _run(["--freeze-artifact", str(freeze)])
    assert cp.returncode == 2, cp.stdout
    assert "contaminated=true" in cp.stdout


def test_validate_freeze_contaminated_override(tmp_path: Path) -> None:
    csv_path = tmp_path / "sweep.csv"
    checkpoint = tmp_path / "checkpoint.json"
    freeze = tmp_path / "chosen.json"
    _write_csv(csv_path, [{"abstain": "0.6", "uncertain": "0.8", "contaminated": "true"}])
    _write_checkpoint(checkpoint, status="complete")
    _write_freeze(freeze, csv_path=csv_path, checkpoint_path=checkpoint)
    cp = _run(["--freeze-artifact", str(freeze), "--allow-contaminated-freeze"])
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_validate_freeze_fails_for_incomplete_checkpoint(tmp_path: Path) -> None:
    csv_path = tmp_path / "sweep.csv"
    checkpoint = tmp_path / "checkpoint.json"
    freeze = tmp_path / "chosen.json"
    _write_csv(csv_path, [{"abstain": "0.6", "uncertain": "0.8", "contaminated": "false"}])
    _write_checkpoint(checkpoint, status="partial")
    _write_freeze(freeze, csv_path=csv_path, checkpoint_path=checkpoint)
    cp = _run(["--freeze-artifact", str(freeze)])
    assert cp.returncode == 2, cp.stdout
    assert "checkpoint status must be 'complete'" in cp.stdout


def test_validate_freeze_with_eval_crosscheck(tmp_path: Path) -> None:
    csv_path = tmp_path / "sweep.csv"
    checkpoint = tmp_path / "checkpoint.json"
    freeze = tmp_path / "chosen.json"
    eval_result = tmp_path / "eval.json"
    _write_csv(csv_path, [{"abstain": "0.6", "uncertain": "0.8", "contaminated": "false"}])
    _write_checkpoint(checkpoint, status="complete")
    _write_freeze(freeze, csv_path=csv_path, checkpoint_path=checkpoint)
    eval_result.write_text(
        json.dumps(
            {
                "policy": {
                    "effective": {
                        "pipeline_policy_version_key": "v2",
                        "confidence_abstain_threshold": 0.6,
                        "confidence_uncertain_threshold": 0.8,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    cp = _run(["--freeze-artifact", str(freeze), "--eval-result", str(eval_result)])
    assert cp.returncode == 0, cp.stdout + cp.stderr
