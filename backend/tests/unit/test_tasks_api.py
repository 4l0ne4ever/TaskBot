import uuid
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import tasks as tasks_api, conflicts as conflicts_api
from app.api.deps import get_current_user
from app.models.conflict import Conflict
from app.models.task import Task
from app.models.user import User


_USER_ID = uuid.uuid4()
_TASK_ID = uuid.uuid4()
_TASK_2_ID = uuid.uuid4()
_CONFLICT_ID = uuid.uuid4()


def _make_user() -> User:
    return User(id=_USER_ID, email="test@example.com")


def _make_task(tid: uuid.UUID = _TASK_ID, **overrides) -> Task:
    defaults = {
        "id": tid,
        "user_id": _USER_ID,
        "source_doc_id": None,
        "title": "Submit report",
        "assignee": "Alice",
        "deadline": date(2026, 5, 1),
        "priority": "high",
        "missing_fields": [],
        "status": "pending",
        "calendar_event_id": None,
        "notification_sent": False,
        "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Task(**defaults)


def _make_conflict() -> Conflict:
    return Conflict(
        id=_CONFLICT_ID,
        user_id=_USER_ID,
        conflict_type="deadline_conflict",
        description="Different deadlines",
        source_a_ref="a",
        source_b_ref="b",
        task_ids=[_TASK_ID],
        resolved=False,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def scalars(self):
        return _FakeScalars(self._rows)

    def scalar_one_or_none(self):
        return self._one


class _FakeDB:
    def __init__(self, tasks=None, conflicts=None):
        self._tasks = tasks or []
        self._conflicts = conflicts or []
        self.deleted = []

    async def execute(self, stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        if "conflicts" in compiled:
            for c in self._conflicts:
                return _FakeResult(rows=self._conflicts, one=c)
            return _FakeResult(rows=self._conflicts)
        for t in self._tasks:
            return _FakeResult(rows=self._tasks, one=t)
        return _FakeResult(rows=self._tasks)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        pass

    async def rollback(self):
        pass


def _build_app(fake_db: _FakeDB, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(conflicts_api.router, prefix="/tasks/conflicts")
    app.include_router(tasks_api.router, prefix="/tasks")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[tasks_api.get_db] = _override_get_db
    app.dependency_overrides[conflicts_api.get_db] = _override_get_db
    if user:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def test_list_tasks_returns_user_tasks() -> None:
    user = _make_user()
    t1 = _make_task()
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Submit report"
    assert data[0]["id"] == str(_TASK_ID)


def test_get_task_by_id() -> None:
    user = _make_user()
    t1 = _make_task()
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.get(f"/tasks/{_TASK_ID}")
    assert r.status_code == 200
    assert r.json()["title"] == "Submit report"


def test_get_task_not_found() -> None:
    user = _make_user()
    db = _FakeDB(tasks=[])
    client = TestClient(_build_app(db, user))
    r = client.get(f"/tasks/{uuid.uuid4()}")
    assert r.status_code == 404


def test_patch_task_updates_fields() -> None:
    user = _make_user()
    t1 = _make_task()
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed", "assignee": "Bob"})
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
    assert r.json()["assignee"] == "Bob"


def test_delete_task() -> None:
    user = _make_user()
    t1 = _make_task(calendar_event_id="evt-123")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.delete(f"/tasks/{_TASK_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == str(_TASK_ID)
    assert body["calendar_event_id"] == "evt-123"
    assert len(db.deleted) == 1


def test_list_conflicts_unresolved() -> None:
    user = _make_user()
    c1 = _make_conflict()
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/conflicts?resolved=false")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["conflict_type"] == "deadline_conflict"


def test_resolve_conflict() -> None:
    user = _make_user()
    c1 = _make_conflict()
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/conflicts/{_CONFLICT_ID}", json={"resolution": "accept_a"})
    assert r.status_code == 200
    assert r.json()["resolved"] is True
