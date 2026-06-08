"""Phase 6.6 (recurring events, 2026-06-03): tests for the backend
PATCH /tasks/{id} endpoint behaviours added for recurrence:

  - set a fresh recurrence_rule (validated, canonicalised)
  - empty string clears the active rule (remove-recurrence flow)
  - applying a suggested rule auto-clears recurrence_suggested
  - dismiss_recurrence_suggestion stamps recurrence_dismissed_at
  - invalid RRULE → 422
  - remove-recurrence on a task with deadline shifts deadline to next
    occurrence and clears calendar_event_id
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import tasks as tasks_api
from app.api.deps import get_current_user
from app.models.task import Task
from app.models.user import User


_USER_ID = uuid.uuid4()
_TASK_ID = uuid.uuid4()


def _make_user() -> User:
    return User(id=_USER_ID, email="test@example.com")


def _make_task(**overrides) -> Task:
    defaults = {
        "id": _TASK_ID,
        "user_id": _USER_ID,
        "source_doc_id": None,
        "title": "Weekly sync",
        "assignee": "Anna",
        "deadline": date(2026, 6, 8),  # Monday
        "priority": "high",
        "missing_fields": [],
        "status": "confirmed",
        "calendar_event_id": "gcal-abc-123",
        "notification_sent": True,
        "recurrence_rule": None,
        "recurrence_suggested": None,
        "recurrence_dismissed_at": None,
        "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Task(**defaults)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows=None, one=None, scalar=None):
        self._rows = rows or []
        self._one = one
        self._scalar = scalar

    def scalars(self):
        return _FakeScalars(self._rows)

    def scalar_one_or_none(self):
        return self._one

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    def __init__(self, tasks=None):
        self._tasks = tasks or []
        self.committed = False

    async def execute(self, stmt):
        rows = self._tasks
        one = rows[0] if rows else None
        return _FakeResult(rows=rows, one=one, scalar=len(rows))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


def _build_app(db: _FakeDB, user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(tasks_api.router, prefix="/tasks")

    async def _override_get_db():
        yield db

    app.dependency_overrides[tasks_api.get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


# ── set recurrence_rule ───────────────────────────────────────────────────


def test_patch_sets_recurrence_rule():
    user = _make_user()
    task = _make_task()
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"})
    assert r.status_code == 200, r.text
    assert r.json()["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO"
    assert task.recurrence_rule == "FREQ=WEEKLY;BYDAY=MO"


def test_patch_canonicalises_rrule():
    user = _make_user()
    task = _make_task()
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(
        f"/tasks/{_TASK_ID}", json={"recurrence_rule": "BYDAY=MO;FREQ=WEEKLY;INTERVAL=2"}
    )
    assert r.status_code == 200
    # Validator canonicalises key order.
    assert task.recurrence_rule == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"


def test_patch_invalid_rrule_returns_422():
    user = _make_user()
    task = _make_task()
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(
        f"/tasks/{_TASK_ID}", json={"recurrence_rule": "FREQ=WEEKLY;BYHOUR=9"}
    )
    assert r.status_code == 422
    assert task.recurrence_rule is None  # unchanged


# ── apply suggested → auto-clears recurrence_suggested ───────────────────


def test_apply_suggested_clears_suggestion():
    user = _make_user()
    task = _make_task(recurrence_suggested="FREQ=WEEKLY;BYDAY=MO")
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(
        f"/tasks/{_TASK_ID}", json={"recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"}
    )
    assert r.status_code == 200
    assert task.recurrence_rule == "FREQ=WEEKLY;BYDAY=MO"
    assert task.recurrence_suggested is None


# ── dismiss flag ──────────────────────────────────────────────────────────


def test_dismiss_recurrence_suggestion_sets_timestamp():
    user = _make_user()
    task = _make_task(recurrence_suggested="FREQ=DAILY")
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(
        f"/tasks/{_TASK_ID}", json={"dismiss_recurrence_suggestion": True}
    )
    assert r.status_code == 200
    assert task.recurrence_suggested is None
    assert task.recurrence_dismissed_at is not None


def test_dismiss_false_does_nothing():
    user = _make_user()
    task = _make_task(recurrence_suggested="FREQ=DAILY")
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(
        f"/tasks/{_TASK_ID}", json={"dismiss_recurrence_suggestion": False}
    )
    assert r.status_code == 200
    assert task.recurrence_suggested == "FREQ=DAILY"
    assert task.recurrence_dismissed_at is None


# ── remove-recurrence flow ────────────────────────────────────────────────


def test_remove_recurrence_shifts_deadline_and_clears_calendar_event():
    """Empty string clears active rule. Deadline moves to next occurrence
    of the prior rule. calendar_event_id is wiped so the next dispatch
    recreates as a single event (the orphan in Google Calendar is a
    documented v1 limitation)."""
    user = _make_user()
    # Anchor deadline = 2026-01-05 (Mon, far in the past relative to today).
    task = _make_task(
        deadline=date(2026, 1, 5),
        recurrence_rule="FREQ=WEEKLY;BYDAY=MO",
        calendar_event_id="gcal-old-recurring",
    )
    db = _FakeDB(tasks=[task])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"recurrence_rule": ""})
    assert r.status_code == 200, r.text
    assert task.recurrence_rule is None
    assert task.calendar_event_id is None
    # next Monday >= today (test runs after 2026-06-04).
    assert task.deadline is not None
    assert task.deadline.weekday() == 0  # Monday
    assert task.deadline >= date(2026, 6, 4)
