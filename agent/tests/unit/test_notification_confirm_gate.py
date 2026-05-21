"""Unit tests for the Phase 7.3 calendar dispatch gate.

async_dispatch_notifications must only create/update calendar events for
tasks with status="confirmed". Pending and dismissed tasks must be silently
skipped so that users remain in control of what lands on their calendar.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


def _make_task(*, status: str, deadline: str | None, calendar_event_id: str | None = None) -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.status = status
    t.deadline = deadline
    t.calendar_event_id = calendar_event_id
    t.title = "Test task"
    t.notification_sent = False
    return t


def _make_session(tasks: list) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = tasks
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=ctx)
    return session


def _run(state: dict) -> dict:
    import asyncio
    from app.services.notification_service import async_dispatch_notifications
    return asyncio.run(async_dispatch_notifications(state))


def test_confirmed_task_with_deadline_gets_calendar_event(monkeypatch) -> None:
    user_id = uuid.uuid4()
    task = _make_task(status="confirmed", deadline="2026-06-01")

    session = _make_session([task])
    session_factory = MagicMock(return_value=session)

    calendar = AsyncMock()
    calendar.create_event = AsyncMock(return_value={"event_id": "ev-1"})

    import app.services.notification_service as svc
    monkeypatch.setattr(svc, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(svc, "CalendarMCPClient", MagicMock(return_value=calendar))

    result = _run({
        "user_id": str(user_id),
        "access_token": "tok",
        "saved_task_ids": [str(task.id)],
    })

    assert result["errors"] == []
    assert len(result["notifications_sent"]) == 1
    assert result["notifications_sent"][0]["type"] == "calendar"
    calendar.create_event.assert_awaited_once()


def test_pending_task_not_dispatched_to_calendar(monkeypatch) -> None:
    """Pending tasks must produce zero calendar notifications — the confirm gate."""
    user_id = uuid.uuid4()

    session = _make_session([])  # DB returns nothing because status != confirmed
    session_factory = MagicMock(return_value=session)

    calendar = AsyncMock()

    import app.services.notification_service as svc
    monkeypatch.setattr(svc, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(svc, "CalendarMCPClient", MagicMock(return_value=calendar))

    result = _run({
        "user_id": str(user_id),
        "access_token": "tok",
        "saved_task_ids": [str(uuid.uuid4())],
    })

    assert result["errors"] == []
    assert result["notifications_sent"] == []
    calendar.create_event.assert_not_awaited()
    calendar.update_event.assert_not_awaited()


def test_confirmed_task_without_deadline_gets_in_app_reminder(monkeypatch) -> None:
    """Confirmed tasks with no deadline fall back to the in_app_reminder path."""
    user_id = uuid.uuid4()
    task = _make_task(status="confirmed", deadline=None)

    session = _make_session([task])
    session_factory = MagicMock(return_value=session)

    calendar = AsyncMock()

    import app.services.notification_service as svc
    monkeypatch.setattr(svc, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(svc, "CalendarMCPClient", MagicMock(return_value=calendar))

    result = _run({
        "user_id": str(user_id),
        "access_token": "tok",
        "saved_task_ids": [str(task.id)],
    })

    assert result["errors"] == []
    assert len(result["notifications_sent"]) == 1
    assert result["notifications_sent"][0]["type"] == "in_app_reminder"
    calendar.create_event.assert_not_awaited()


def test_confirmed_task_with_existing_event_gets_update(monkeypatch) -> None:
    user_id = uuid.uuid4()
    task = _make_task(status="confirmed", deadline="2026-07-15", calendar_event_id="ev-existing")

    session = _make_session([task])
    session_factory = MagicMock(return_value=session)

    calendar = AsyncMock()
    calendar.update_event = AsyncMock(return_value={"event_id": "ev-existing"})

    import app.services.notification_service as svc
    monkeypatch.setattr(svc, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(svc, "CalendarMCPClient", MagicMock(return_value=calendar))

    result = _run({
        "user_id": str(user_id),
        "access_token": "tok",
        "saved_task_ids": [str(task.id)],
    })

    assert result["errors"] == []
    calendar.update_event.assert_awaited_once()
    calendar.create_event.assert_not_awaited()
