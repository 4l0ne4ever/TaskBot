"""Unit tests for the Weekly Brief (Phase 8.3) — pure aggregation + render.

build_brief_data and render_brief_html are deliberately DB/network-free so the
digest content is testable without a live pipeline.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.services.weekly_brief_service import (
    build_brief_data,
    render_brief_html,
    render_brief_text,
)

_NOW = datetime(2026, 5, 22, 9, 0, tzinfo=UTC)
_TODAY = _NOW.date()


def _task(**kw) -> SimpleNamespace:
    defaults = dict(
        title="Untitled task",
        status="pending",
        confirmed_by=None,
        deadline=None,
        assignee=None,
        assignee_canonical=None,
        missing_fields=None,
        created_at=_NOW,  # "this week" by default
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _conflict(**kw) -> SimpleNamespace:
    defaults = dict(conflict_type="deadline_conflict", scope="multi_source", description="d", resolved=False)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_build_brief_counts_new_and_auto_confirmed() -> None:
    tasks = [
        _task(confirmed_by="system", status="confirmed", assignee_canonical="Minh"),
        _task(confirmed_by="system", status="confirmed", assignee_canonical="Minh"),
        _task(status="pending", confirmed_by=None, assignee_canonical="Lan"),
        # old task: created before the window → not "new", not auto counted
        _task(confirmed_by="system", status="confirmed", created_at=_NOW - timedelta(days=30)),
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    assert data["new_this_week"] == 3
    assert data["auto_confirmed_week"] == 2
    assert data["auto_confirm_rate"] == round(2 / 3, 4)
    assert data["pending_review"] == 1
    assert data["confirmed_total"] == 3  # includes the old confirmed one


def test_build_brief_deadline_buckets_and_dismissed_excluded() -> None:
    tasks = [
        _task(deadline=_TODAY - timedelta(days=1), assignee_canonical="Minh"),  # overdue
        _task(deadline=_TODAY + timedelta(days=3), assignee_canonical="Minh"),  # due 7d
        _task(deadline=_TODAY + timedelta(days=40)),                             # far
        _task(status="dismissed", deadline=_TODAY - timedelta(days=1)),          # excluded
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    assert data["overdue"] == 1
    assert data["due_this_week"] == 1
    minh = next(m for m in data["team"] if m["assignee"] == "Minh")
    assert minh["open"] == 2
    assert minh["overdue"] == 1


def test_build_brief_open_conflicts_only() -> None:
    conflicts = [
        _conflict(conflict_type="deadline_conflict", resolved=False),
        _conflict(conflict_type="assignee_conflict", resolved=True),  # resolved → excluded
    ]
    data = build_brief_data([], conflicts, now=_NOW)
    assert data["open_conflict_count"] == 1
    assert data["open_conflicts"][0]["conflict_type"] == "deadline_conflict"


def test_render_html_contains_key_figures() -> None:
    tasks = [_task(confirmed_by="system", status="confirmed", assignee_canonical="Minh", deadline=_TODAY - timedelta(days=1))]
    data = build_brief_data(tasks, [_conflict()], now=_NOW)
    html = render_brief_html(data)
    assert "TaskBot Weekly Brief" in html
    assert "Minh" in html
    assert "deadline_conflict" in html
    # html-escaped, self-contained
    assert "<div" in html


def test_render_html_escapes_conflict_description() -> None:
    data = build_brief_data([], [_conflict(description="<script>alert(1)</script>")], now=_NOW)
    html = render_brief_html(data)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_text_fallback() -> None:
    data = build_brief_data([_task(assignee_canonical="Lan")], [], now=_NOW)
    text = render_brief_text(data)
    assert "TaskBot Weekly Brief" in text
    assert "Lan" in text


# ── Round 14: outstanding-items section ──────────────────────────────────
# Mirrors the daily-digest backlog: pending OR confirmed-with-missing-fields,
# sorted overdue → due-today → future → no-deadline.


def test_build_brief_collects_outstanding_backlog() -> None:
    tasks = [
        # confirmed + missing field → counts as outstanding
        _task(
            title="Ship landing page",
            status="confirmed",
            confirmed_by="user",
            missing_fields=["deadline"],
            assignee_canonical="Minh",
        ),
        # pending without deadline → counts; sorts last
        _task(title="Pick demo date", status="pending", assignee_canonical="Lan"),
        # pending overdue → counts; sorts first
        _task(
            title="Refactor consumer",
            status="pending",
            deadline=_TODAY - timedelta(days=2),
            assignee_canonical="Hung",
        ),
        # confirmed, no missing fields → NOT outstanding (already handled)
        _task(
            title="Already done",
            status="confirmed",
            confirmed_by="user",
            missing_fields=[],
            deadline=_TODAY + timedelta(days=1),
        ),
        # dismissed → excluded (user already triaged)
        _task(title="Spam", status="dismissed"),
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    assert data["outstanding_total"] == 3
    titles = [s["title"] for s in data["outstanding_samples"]]
    # overdue first, then no-deadline (the "missing deadline" item has no
    # deadline so it sorts after the deadline-bearing rows)
    assert titles[0] == "Refactor consumer"
    assert "Ship landing page" in titles
    assert "Pick demo date" in titles
    assert "Already done" not in titles
    assert "Spam" not in titles


def test_render_html_includes_outstanding_when_present() -> None:
    tasks = [
        _task(title="Pay invoice", status="pending", deadline=_TODAY - timedelta(days=1)),
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    html = render_brief_html(data)
    assert "Open items needing your attention" in html
    assert "Pay invoice" in html


def test_render_html_omits_outstanding_when_empty() -> None:
    # Only auto-confirmed + no missing fields → nothing outstanding.
    tasks = [
        _task(
            title="All clear",
            status="confirmed",
            confirmed_by="system",
            missing_fields=[],
        ),
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    html = render_brief_html(data)
    assert data["outstanding_total"] == 0
    assert "Open items needing your attention" not in html


def test_render_text_includes_outstanding_with_urgency_markers() -> None:
    tasks = [
        _task(title="Late task", status="pending", deadline=_TODAY - timedelta(days=3)),
        _task(title="Today task", status="pending", deadline=_TODAY),
    ]
    data = build_brief_data(tasks, [], now=_NOW)
    text = render_brief_text(data)
    assert "Open items needing your attention" in text
    assert "[OVERDUE]" in text
    assert "[TODAY]" in text
