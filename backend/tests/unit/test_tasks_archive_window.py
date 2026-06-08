"""Tests for the GET /tasks ?scope= filter.

Three mutually-exclusive modes (2026-06-07 v2):

  scope="active"    → NOT done AND NOT past-due-confirmed (default)
  scope="completed" → done OR past-due-confirmed (the Show-completed view)
  scope="all"       → no completed-bucket filter (used by /tracking Kanban
                      so the Done column stays populated)

History:
- v1 had a 30-day auto-archive window — dropped (user feedback: multi-tier
  UX was confusing).
- v1.5 used ``include_archived=true`` (additive: show all). Renamed because
  the toggle in /tasks UI is now "Show completed", which reads as the
  completed-bucket view, not "show everything".
- v2 (current) uses ``scope`` enum so /tasks (binary toggle) and /tracking
  (needs full board) can pick the predicate they actually want.

Tests assert the SQL the API emits — a fake DB returns the row set, so
end-to-end the wire contract is exercised.
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


def _make_user() -> User:
    return User(id=_USER_ID, email="test@example.com")


def _make_task(**overrides) -> Task:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": _USER_ID,
        "source_doc_id": None,
        "title": "Submit report",
        "assignee": "Alice",
        "deadline": date(2026, 6, 1),
        "priority": "high",
        "missing_fields": [],
        "status": "pending",
        "calendar_event_id": None,
        "notification_sent": False,
        "progress_state": None,
        "recurrence_rule": None,
        "recurrence_suggested": None,
        "recurrence_dismissed_at": None,
        "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Task(**defaults)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return _FakeScalars(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    """Captures the compiled SQL of the last list_tasks call so a test can
    assert the predicate the API emitted. Returns all stored tasks for the
    initial select (the API filtering happens at SQL level in real life)."""

    def __init__(self, tasks=None):
        self._tasks = tasks or []
        self.captured_sql: list[str] = []

    async def execute(self, stmt):
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        self.captured_sql.append(compiled)
        low = compiled.lower()
        if "count(" in low:
            return _FakeResult(scalar=len(self._tasks))
        return _FakeResult(rows=self._tasks)

    async def commit(self):
        pass


def _build_app(db: _FakeDB, user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(tasks_api.router, prefix="/tasks")

    async def _override_get_db():
        yield db

    app.dependency_overrides[tasks_api.get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _last_select_sql(db: _FakeDB) -> str:
    for sql in reversed(db.captured_sql):
        if "count(" not in sql.lower():
            return sql.lower()
    return ""


# ── scope=active (default): hide done + past-due-confirmed ──────────────


def test_default_scope_emits_active_predicate():
    user = _make_user()
    db = _FakeDB(tasks=[_make_task(progress_state="done")])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Active predicate: IS DISTINCT FROM 'done' + NOT past-due-confirmed
    assert "is distinct from 'done'" in sql
    assert "'confirmed'" in sql


def test_default_scope_uses_today_for_past_due():
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    assert date.today().isoformat() in sql


def test_scope_active_explicit_matches_default():
    """Explicit ``scope=active`` emits the same SQL as the default."""
    user = _make_user()
    db_default = _FakeDB(tasks=[])
    client_default = TestClient(_build_app(db_default, user))
    client_default.get("/tasks")

    db_explicit = _FakeDB(tasks=[])
    client_explicit = TestClient(_build_app(db_explicit, user))
    client_explicit.get("/tasks?scope=active")

    # Same predicates appear in both — IS DISTINCT FROM and past-due clause.
    sql_default = _last_select_sql(db_default)
    sql_explicit = _last_select_sql(db_explicit)
    assert "is distinct from 'done'" in sql_default
    assert "is distinct from 'done'" in sql_explicit


# ── scope=completed: only done OR past-due-confirmed ────────────────────


def test_scope_completed_flips_predicate():
    """``scope=completed`` shows the inverse of active: only rows where
    progress_state='done' OR (status='confirmed' AND deadline<today).
    The active-list exclusion clauses must NOT appear — they would
    contradict the inverted view."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks?scope=completed")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Positive inclusion: equality with 'done' (not IS DISTINCT FROM)
    assert "progress_state = 'done'" in sql
    assert "'confirmed'" in sql
    assert date.today().isoformat() in sql
    # The active-list exclusion (IS DISTINCT FROM) must NOT appear when
    # completed is requested — we want done rows, not their complement.
    assert "is distinct from 'done'" not in sql


def test_scope_completed_excludes_null_progress_null_deadline():
    """A row with progress=NULL and deadline=NULL is neither 'done' (NULL
    fails equality) nor 'past-due-confirmed' (NULL deadline fails the
    range guard). The completed view must not include it — that would
    surface a fresh pending task as 'completed'."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks?scope=completed")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Positive clause: progress_state = 'done'
    assert "progress_state = 'done'" in sql
    # Past-due branch is guarded by IS NOT NULL so NULL-deadline rows
    # don't accidentally satisfy ``deadline < today``.
    assert "deadline is not null" in sql


# ── scope=all: no completed-bucket filter ───────────────────────────────


def test_scope_all_emits_no_completed_filter():
    """``scope=all`` lifts the completed-bucket filter entirely — every
    non-archived row passes. Neither the active-list exclusion nor the
    completed-list inclusion clauses appear."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks?scope=all")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Neither the active exclusion nor the completed positive clause
    # appear; today's date is no longer in the WHERE for completed-filtering.
    assert "is distinct from 'done'" not in sql
    # progress_state = 'done' is the completed-view positive predicate;
    # absent in scope=all.
    assert "progress_state = 'done'" not in sql


# ── NULL-safety regression: active view keeps no-deadline pending ───────


def test_default_keeps_rows_with_null_progress_and_null_deadline():
    """Regression for 2026-06-07: a naïve ``progress_state='done' OR (...)``
    predicate evaluates to NULL when both sides are NULL; SQL drops the
    row on ``NOT NULL``. The active default view must keep pending tasks
    with no deadline (the most common new-task shape)."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Fix uses ``IS DISTINCT FROM 'done'`` so NULL progress_state survives.
    assert "is distinct from 'done'" in sql
    # Past-due clause guarded by ``deadline IS NOT NULL`` so a no-deadline
    # task is not silently filtered.
    assert "deadline is not null" in sql


# ── legacy params silently ignored ──────────────────────────────────────


def test_legacy_include_archived_param_ignored():
    """``include_archived`` was the v1.5 param name. FastAPI ignores
    unknown query params by default — the important contract is that the
    response is still 200 and the SQL matches the default active scope."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks?include_archived=true")
    assert r.status_code == 200
    sql = _last_select_sql(db)
    # Unknown param ignored → default active-scope SQL emitted.
    assert "is distinct from 'done'" in sql
    # The completed-scope positive predicate must NOT leak in.
    assert "progress_state = 'done'" not in sql


def test_invalid_scope_value_rejected():
    """An unknown ``scope`` value returns 422 (Pydantic regex validation).
    Keeps the contract honest: callers can't silently get a different view."""
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks?scope=archived")
    assert r.status_code == 422
