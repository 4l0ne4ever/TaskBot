"""Conflict metric scope: skip GT conflict rows without eval_existing_tasks fixture."""
from __future__ import annotations

from metrics import aggregate, evaluate_sample


def test_conflict_skipped_when_gt_conflict_but_no_fixture():
    expected = {
        "tasks": [{"title": "T1", "assignee": "A", "deadline": "2026-04-01"}],
        "conflicts": [{"type": "deadline_conflict", "task_title": "T1"}],
    }
    predicted = {"tasks": [], "conflicts": []}
    sample = {"id": "x", "expected": expected}
    scores = evaluate_sample(expected, predicted, sample)
    assert scores["conflict_eval_skipped"] is True
    assert scores["conflict"]["tp"] == scores["conflict"]["fp"] == scores["conflict"]["fn"] == 0


def test_conflict_scored_when_fixture_present():
    expected = {
        "tasks": [{"title": "T1", "assignee": "A", "deadline": "2026-04-01"}],
        "conflicts": [{"type": "deadline_conflict", "task_title": "T1"}],
    }
    predicted = {"tasks": [], "conflicts": [{"type": "deadline_conflict"}]}
    sample = {
        "id": "y",
        "eval_existing_tasks": [{"title": "T1", "assignee": "A", "deadline": "2026-04-03"}],
    }
    scores = evaluate_sample(expected, predicted, sample)
    assert scores["conflict_eval_skipped"] is False
    assert scores["conflict"]["tp"] == 1


def test_aggregate_omits_skipped_conflict_counts():
    base = {
        "title": {"tp": 1, "fp": 0, "fn": 0},
        "assignee": {"tp": 0, "fp": 0, "fn": 0},
        "deadline": {"exact": 0, "near": 0, "total": 0},
        "abstention": {"expected_empty": False, "pred_empty": False, "correct_abstain": False, "false_answer_on_empty": False, "false_abstain_on_nonempty": False},
        "calibration_bins": [{"n": 0, "correct": 0} for _ in range(5)],
    }
    skipped = {
        **base,
        "conflict": {"tp": 0, "fp": 0, "fn": 0},
        "conflict_eval_skipped": True,
        "sample_id": "a",
        "category": "conflict_deadline",
    }
    scored = {
        **base,
        "conflict": {"tp": 0, "fp": 1, "fn": 1},
        "conflict_eval_skipped": False,
        "sample_id": "b",
        "category": "conflict_deadline",
    }
    out = aggregate([skipped, scored])
    assert out["counts"]["conflict_eval_samples_skipped"] == 1
    assert out["counts"]["conflict_eval_samples_scoped"] == 1
    assert out["conflict_f1"]["f1"] == 0.0
    assert out["conflict_f1"]["precision"] == 0.0 and out["conflict_f1"]["recall"] == 0.0
