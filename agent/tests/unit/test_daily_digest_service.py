"""Unit tests for the Daily Digest service (Round 9, 2026-05-30).

Covers the two pure layers (``build_digest_data`` and the two renderers) plus
the schedule/window contract. The send-side handler is tested in
``test_queue_consumer_daily_digest.py`` because the handler is identical-shape
to the Weekly Brief handler.

Window contract: ``DAILY_DIGEST_WINDOW_HOURS = 24`` rolling from ``now``.
Pending-review count is a *snapshot* of current state, not a window — the user
wants to see "what still needs me" right now, not "what showed up in the
window".
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.services.daily_digest_service import (
    DAILY_DIGEST_WINDOW_HOURS,
    build_digest_data,
    render_digest_html,
    render_digest_text,
)


_NOW = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)  # 18:00 ICT
_WITHIN = _NOW - timedelta(hours=DAILY_DIGEST_WINDOW_HOURS - 1)
_OUTSIDE = _NOW - timedelta(hours=DAILY_DIGEST_WINDOW_HOURS + 1)


def _task(**kw):
    defaults = dict(
        id="t", title="x", status="pending", confirmed_by=None, deadline=None,
        assignee=None, missing_fields=None, created_at=_WITHIN,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _conflict(**kw):
    defaults = dict(resolved=False, created_at=_WITHIN)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_window_excludes_tasks_created_more_than_24h_ago():
    inside = _task(created_at=_WITHIN, confirmed_by="system", status="confirmed")
    outside = _task(created_at=_OUTSIDE, confirmed_by="system", status="confirmed")
    data = build_digest_data([inside, outside], [], now=_NOW)
    # Only the inside task counts toward today's counters.
    assert data["new_today"] == 1
    assert data["auto_confirmed_today"] == 1


def test_auto_confirmed_today_excludes_user_confirmed():
    auto = _task(confirmed_by="system", status="confirmed")
    by_user = _task(confirmed_by="user", status="confirmed")
    data = build_digest_data([auto, by_user], [], now=_NOW)
    assert data["auto_confirmed_today"] == 1
    assert data["user_confirmed_today"] == 1


def test_pending_review_is_snapshot_not_windowed():
    """Pending tasks count toward ``pending_review_now`` regardless of age —
    the user wants to see everything that still needs them, not just stuff
    that landed today."""
    today_pending = _task(status="pending", created_at=_WITHIN, title="today")
    week_old_pending = _task(status="pending", created_at=_OUTSIDE, title="old")
    data = build_digest_data([today_pending, week_old_pending], [], now=_NOW)
    assert data["pending_review_now"] == 2


def test_overdue_and_due_today_classification():
    yesterday = (_NOW.date() - timedelta(days=1))
    today = _NOW.date()
    tomorrow = (_NOW.date() + timedelta(days=1))
    overdue = _task(status="confirmed", deadline=yesterday)
    today_task = _task(status="confirmed", deadline=today)
    future = _task(status="confirmed", deadline=tomorrow)
    data = build_digest_data([overdue, today_task, future], [], now=_NOW)
    assert data["overdue_now"] == 1
    assert data["due_today"] == 1
    # ``due_today`` does not include the future task; the future task does not
    # appear in either bucket — correctly invisible until its day.


def test_conflicts_today_vs_open_snapshot():
    new_open = _conflict(resolved=False, created_at=_WITHIN)
    old_open = _conflict(resolved=False, created_at=_OUTSIDE)
    new_resolved = _conflict(resolved=True, created_at=_WITHIN)
    data = build_digest_data([], [new_open, old_open, new_resolved], now=_NOW)
    # conflicts_today is windowed (includes both new_open and new_resolved);
    # open_conflicts is the snapshot of unresolved (excludes new_resolved).
    assert data["conflicts_today"] == 2
    assert data["open_conflicts"] == 2


def test_review_samples_capped_and_carry_missing_fields():
    tasks = [
        _task(status="pending", title=f"task{i}", missing_fields=["deadline"])
        for i in range(20)
    ]
    data = build_digest_data(tasks, [], now=_NOW)
    assert data["pending_review_now"] == 20
    assert len(data["review_samples"]) == 8  # _MAX_REVIEW_TASKS_SHOWN
    assert data["review_samples"][0]["missing"] == ["deadline"]


def test_render_text_includes_headline_counts():
    data = build_digest_data(
        [
            _task(status="confirmed", confirmed_by="system"),
            _task(status="pending", title="needs you", missing_fields=["assignee"]),
        ],
        [],
        now=_NOW,
    )
    text = render_digest_text(data)
    assert "Auto-confirmed today : 1" in text
    assert "Need your review     : 1" in text
    assert "needs you" in text
    assert "missing: assignee" in text


def test_render_html_escapes_user_content():
    """No raw HTML can leak from a task title — guards against an attacker
    sending an email with HTML in the subject/title."""
    data = build_digest_data(
        [_task(status="pending", title="<script>alert(1)</script>")],
        [],
        now=_NOW,
    )
    html_out = render_digest_html(data)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_empty_data_renders_clean_slate_message():
    data = build_digest_data([], [], now=_NOW)
    text = render_digest_text(data)
    assert "Auto-confirmed today : 0" in text
    assert "(nothing — clean slate)" in text
