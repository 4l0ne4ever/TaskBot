"""Unit tests for the runtime-error contamination gate in
``sweep_policy_thresholds.py`` (RC #18, pass 7).

Rationale: when a sweep cell hits shared environmental failures (Groq TPD
exhaustion, transport errors), ``run_eval`` marks samples as runtime errors
and their predictions collapse into ``{"tasks": []}`` which dilutes title/
assignee F1 into a false low number. A policy threshold can then *look*
awful only because it happened to run during a rate-limit window. Mirroring
the ``contaminated`` flag added in pass 2 for fallback-model routing, we now
flag cells whose runtime-error share exceeds a tolerance so
``_pick_best_row`` won't select them.

These tests exercise the classifier in isolation — they don't run the full
sweep.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEP_DIR = ROOT / "eval"
sys.path.insert(0, str(SWEEP_DIR))

sweep = importlib.import_module("sweep_policy_thresholds")


def test_fallback_contamination_dominates(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    contaminated, reason = sweep._classify_contamination(
        fb_samples=1,
        runtime_count=0,
        runtime_kinds={},
        total_samples=24,
    )
    assert contaminated is True
    assert reason == "fallback"


def test_no_runtime_errors_is_clean(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=0,
        runtime_kinds={},
        total_samples=24,
    )
    assert contaminated is False
    assert reason is None


def test_majority_daily_quota_flags_runtime_tpd(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    monkeypatch.setenv("EVAL_SWEEP_RUNTIME_TOLERANCE", "0.1")
    # 13 runtime errors, 10 of them daily_quota on a 24-sample cell => tpd
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=13,
        runtime_kinds={"daily_quota": 10, "other": 3},
        total_samples=24,
    )
    assert contaminated is True
    assert reason == "runtime_tpd"


def test_small_runtime_count_under_tolerance_is_clean(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    # 1 runtime error out of 24 samples with tolerance 0.1 -> threshold=2 => clean
    monkeypatch.setenv("EVAL_SWEEP_RUNTIME_TOLERANCE", "0.1")
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=1,
        runtime_kinds={"daily_quota": 1},
        total_samples=24,
    )
    assert contaminated is False
    assert reason is None


def test_allow_runtime_errors_escape_hatch(monkeypatch):
    monkeypatch.setenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", "1")
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=24,
        runtime_kinds={"daily_quota": 24},
        total_samples=24,
    )
    assert contaminated is False
    assert reason is None


def test_generic_runtime_errors_flag_runtime_other(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    monkeypatch.setenv("EVAL_SWEEP_RUNTIME_TOLERANCE", "0.1")
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=10,
        runtime_kinds={"other": 10},
        total_samples=24,
    )
    assert contaminated is True
    assert reason == "runtime_other"


def test_majority_organization_restricted_flags_runtime_org_restricted(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS", raising=False)
    monkeypatch.setenv("EVAL_SWEEP_RUNTIME_TOLERANCE", "0.1")
    contaminated, reason = sweep._classify_contamination(
        fb_samples=0,
        runtime_count=10,
        runtime_kinds={"organization_restricted": 10},
        total_samples=24,
    )
    assert contaminated is True
    assert reason == "runtime_org_restricted"


def test_stop_on_daily_quota_defaults_to_true(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_STOP_ON_DAILY_QUOTA", raising=False)
    assert sweep._stop_on_daily_quota() is True


def test_stop_on_daily_quota_can_be_disabled(monkeypatch):
    monkeypatch.setenv("EVAL_SWEEP_STOP_ON_DAILY_QUOTA", "0")
    assert sweep._stop_on_daily_quota() is False


def test_stop_on_organization_restricted_defaults_to_true(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_STOP_ON_ORGANIZATION_RESTRICTED", raising=False)
    assert sweep._stop_on_organization_restricted() is True


def test_stop_on_organization_restricted_can_be_disabled(monkeypatch):
    monkeypatch.setenv("EVAL_SWEEP_STOP_ON_ORGANIZATION_RESTRICTED", "0")
    assert sweep._stop_on_organization_restricted() is False


def test_require_clean_candidate_defaults_to_true(monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_REQUIRE_CLEAN_CANDIDATE", raising=False)
    assert sweep._require_clean_candidate() is True


def test_require_clean_candidate_can_be_disabled(monkeypatch):
    monkeypatch.setenv("EVAL_SWEEP_REQUIRE_CLEAN_CANDIDATE", "0")
    assert sweep._require_clean_candidate() is False


def test_row_fieldnames_include_new_abort_metadata():
    names = sweep._row_fieldnames(
        [
            {
                "abstain": 0.55,
                "uncertain": 0.76,
                "aborted_early": True,
                "abort_reason": "daily_quota",
                "samples_completed": 1,
                "samples_requested": 250,
                "contaminated": True,
            }
        ]
    )
    assert "aborted_early" in names
    assert "abort_reason" in names
    assert names.index("aborted_early") < names.index("contaminated")


def test_lock_path_is_derived_from_checkpoint(tmp_path):
    cp = tmp_path / "abc_checkpoint.json"
    lock = sweep._lock_path_for(cp)
    assert lock.name.endswith(".json.lock")


def test_acquire_and_release_lock(tmp_path, monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_DISABLE_LOCK", raising=False)
    lock = tmp_path / "sweep.lock"
    sweep._acquire_lock(lock)
    assert lock.is_file()
    sweep._release_lock(lock)
    assert not lock.exists()


def test_acquire_lock_fails_if_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("EVAL_SWEEP_DISABLE_LOCK", raising=False)
    lock = tmp_path / "sweep.lock"
    lock.write_text("{}", encoding="utf-8")
    try:
        sweep._acquire_lock(lock)
    except SystemExit as exc:
        assert "sweep lock exists" in str(exc)
    else:
        raise AssertionError("expected SystemExit when lock file already exists")


def test_disable_lock_escape_hatch(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_SWEEP_DISABLE_LOCK", "1")
    lock = tmp_path / "sweep.lock"
    sweep._acquire_lock(lock)
    assert not lock.exists()


def test_reset_sweep_artifacts_removes_checkpoint_csv_and_cell_json(tmp_path):
    cp = tmp_path / "sweep_checkpoint.json"
    csv_path = tmp_path / "sweep.csv"
    lock = sweep._lock_path_for(cp)
    cp.write_text("{}", encoding="utf-8")
    csv_path.write_text("a,b\n", encoding="utf-8")
    lock.write_text("{}", encoding="utf-8")
    j1 = tmp_path / "_sweep_a0.55_u0.76.json"
    j1.write_text("{}", encoding="utf-8")
    r1 = tmp_path / "_sweep_a0.55_u0.76_report.md"
    r1.write_text("#", encoding="utf-8")
    keep = tmp_path / "chosen.json"
    keep.write_text("{}", encoding="utf-8")
    sweep._reset_sweep_artifacts(cp, csv_path, tmp_path)
    assert not cp.exists()
    assert not csv_path.exists()
    assert not lock.exists()
    assert not j1.exists()
    assert not r1.exists()
    assert keep.is_file()
