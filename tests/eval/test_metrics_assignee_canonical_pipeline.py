"""Q-05 — metric-level integration of the canonical-by-data assignee path.

These tests verify that when a prediction / label carries an
``assignee_canonical`` field (stamped by the pipeline via
``AssigneeResolver``), the metric function prefers that over the legacy
rubric-prefix bridge. The rubric bridge remains as a fallback only for
pre-canonical predictions (baselines, old snapshots).
"""
from __future__ import annotations

from metrics import evaluate_sample


def _ass(exp: list[dict], pred: list[dict]) -> dict:
    detail = evaluate_sample({"tasks": exp, "conflicts": []}, {"tasks": pred, "conflicts": []})
    return detail["assignee"]


def test_canonical_field_is_preferred_over_rubric_bridge(monkeypatch):
    """Pipeline stamps ``assignee_canonical="Hương"`` while raw differs
    (``"Bạn Hương"``). The metric must use the canonical, not re-run the
    rubric bridge on the raw — a future prompt change that widens the raw
    field shouldn't silently re-break metrics."""
    monkeypatch.setenv("EVAL_CANONICAL_ASSIGNEE", "1")
    expected = [{"title": "báo cáo", "assignee": "Hương", "assignee_canonical": "Hương"}]
    predicted = [
        {"title": "báo cáo", "assignee": "Bạn Hương", "assignee_canonical": "Hương"},
    ]
    a = _ass(expected, predicted)
    assert a == {"tp": 1, "fp": 0, "fn": 0}


def test_canonical_absent_falls_back_to_rubric_bridge(monkeypatch):
    """Baselines without the resolver don't emit ``assignee_canonical`` —
    the metric must still match "Bạn Hương" ~= "Hương" via the rubric bridge
    so old baselines keep scoring."""
    monkeypatch.setenv("EVAL_CANONICAL_ASSIGNEE", "1")
    expected = [{"title": "báo cáo", "assignee": "Hương"}]
    predicted = [{"title": "báo cáo", "assignee": "Bạn Hương"}]
    a = _ass(expected, predicted)
    assert a["tp"] == 1


def test_canonical_mismatch_counts_as_fp_and_fn(monkeypatch):
    """If the pipeline resolved canonical to someone else entirely, the
    metric must NOT give credit. The canonical field is a stronger signal,
    not a shield against genuine errors."""
    monkeypatch.setenv("EVAL_CANONICAL_ASSIGNEE", "1")
    expected = [{"title": "báo cáo", "assignee": "Hương", "assignee_canonical": "Hương"}]
    predicted = [{"title": "báo cáo", "assignee": "Tuấn", "assignee_canonical": "Tuấn"}]
    a = _ass(expected, predicted)
    assert a["tp"] == 0 and a["fp"] == 1 and a["fn"] == 1


def test_canonical_disabled_uses_raw_assignee(monkeypatch):
    """Ops escape hatch: ``EVAL_CANONICAL_ASSIGNEE=0`` stress-tests raw prompt
    output — the canonical field is ignored and raw strings compared
    directly. Raw "Bạn Hương" (normalized) differs enough from "Hương" that
    the 0.8 title_sim threshold in ``_normalize`` won't match → TP=0."""
    monkeypatch.setenv("EVAL_CANONICAL_ASSIGNEE", "0")
    expected = [{"title": "báo cáo", "assignee": "Hương", "assignee_canonical": "Hương"}]
    predicted = [{"title": "báo cáo", "assignee": "Bạn Hương", "assignee_canonical": "Hương"}]
    a = _ass(expected, predicted)
    assert a["tp"] == 0
