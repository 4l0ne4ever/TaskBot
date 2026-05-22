import json
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import tasks as tasks_api, conflicts as conflicts_api
from app.api.deps import get_current_user
from app.models.conflict import Conflict
from app.models.source_document import SourceDocument
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


def _make_conflict(
    *,
    cid: uuid.UUID | None = None,
    scope: str | None = None,
    conflict_type: str = "deadline_conflict",
) -> Conflict:
    return Conflict(
        id=cid or _CONFLICT_ID,
        user_id=_USER_ID,
        conflict_type=conflict_type,
        description="Different deadlines",
        source_a_ref="a",
        source_b_ref="b",
        task_ids=[_TASK_ID],
        scope=scope,
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
    def __init__(self, tasks=None, conflicts=None, source_docs=None):
        self._tasks = tasks or []
        self._conflicts = conflicts or []
        self._source_docs = source_docs or []
        self.deleted = []
        self.last_sql: str | None = None
        self.committed = False

    async def execute(self, stmt):
        # Render with literal_binds=True so tests can match scope strings
        # ("multi_source", etc.) directly in the compiled SQL rather than
        # having to recognise placeholder markers.
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        self.last_sql = compiled
        low = compiled.lower()
        # Route by the table the statement targets. source_documents is checked
        # first because a Task-with-join query can mention both, but the source
        # endpoints under test issue simple single-table selects.
        if "source_documents" in low and "from source_documents" in low:
            rows = self._source_docs
        elif "conflicts" in low:
            rows = self._conflicts
        else:
            rows = self._tasks
        one = rows[0] if rows else None
        return _FakeResult(rows=rows, one=one)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True

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


def test_get_task_includes_evidence_quote() -> None:
    """Phase 7.1: the evidence highlight UI reads evidence_quote from the task
    response — if it falls off the model the highlight silently disappears."""
    user = _make_user()
    t1 = _make_task(evidence_quote="trước thứ Sáu tuần này")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.get(f"/tasks/{_TASK_ID}")
    assert r.status_code == 200
    assert r.json()["evidence_quote"] == "trước thứ Sáu tuần này"


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


def test_list_conflicts_response_includes_scope_field() -> None:
    """Phase 2.3 UI reads ``scope`` from this response shape — if it ever
    falls off the Pydantic model we'd silently lose badge rendering."""
    user = _make_user()
    c1 = _make_conflict(scope="thread_update")
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/conflicts")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["scope"] == "thread_update"


def test_list_conflicts_scope_filter_param_accepted() -> None:
    """``?scope=...`` is plumbed through to the WHERE clause; the mock DB
    returns whatever it has, but the request must not 422 and the SQL
    fragment must include the ``conflicts.scope`` predicate."""
    user = _make_user()
    c1 = _make_conflict(scope="multi_source")
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/conflicts?scope=multi_source")
    assert r.status_code == 200, r.text
    # The fake DB captured the compiled SQL via _FakeDB.execute; verify the
    # scope filter actually reached the query.
    assert db.last_sql is not None and "conflicts.scope" in db.last_sql


def test_list_conflicts_priority_sort_param_emits_case_order() -> None:
    """``?sort=priority`` must compile to a CASE-based ORDER BY so the
    hierarchy (multi_source > thread_update > inter_doc > intra_batch)
    is enforced at the DB layer rather than in Python."""
    user = _make_user()
    c1 = _make_conflict(scope="multi_source")
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/conflicts?sort=priority")
    assert r.status_code == 200, r.text
    assert db.last_sql is not None
    sql = db.last_sql.lower()
    # CASE expression rendered with our 4 scope branches.
    assert "case" in sql
    assert "multi_source" in sql or "%(param_1)s" in sql  # bound-param fallback


def test_list_conflicts_invalid_sort_rejected() -> None:
    user = _make_user()
    db = _FakeDB(conflicts=[])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/conflicts?sort=garbage")
    assert r.status_code == 422


def test_resolve_conflict() -> None:
    user = _make_user()
    c1 = _make_conflict()
    db = _FakeDB(conflicts=[c1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/conflicts/{_CONFLICT_ID}", json={"resolution": "accept_a"})
    assert r.status_code == 200
    assert r.json()["resolved"] is True


# ── Phase 2.3 Commit 6: thread_update field merge ──────────────────────────────


def _make_source_doc(
    *, doc_id: uuid.UUID, source_type: str = "gmail", source_ref: str = "msg-abc", raw_text: str | None = "Body text"
) -> SourceDocument:
    return SourceDocument(
        id=doc_id,
        user_id=_USER_ID,
        source_type=source_type,
        source_ref=source_ref,
        content_hash="hash",
        raw_text=raw_text,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def _merge_conflict_with_tasks(scope: str = "thread_update", task_ids=None) -> Conflict:
    return Conflict(
        id=_CONFLICT_ID,
        user_id=_USER_ID,
        conflict_type="deadline_conflict",
        description="Thread updated the deadline",
        source_a_ref="a",
        source_b_ref="b",
        task_ids=task_ids if task_ids is not None else [_TASK_2_ID, _TASK_ID],
        scope=scope,
        resolved=False,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def test_merge_applies_fields_dismisses_source_and_skips_calendar() -> None:
    """Older task survives with the newer task's chosen fields; newer task is
    dismissed; no calendar event ⇒ calendar_sync skipped, never enqueued."""
    user = _make_user()
    old = _make_task(
        tid=_TASK_ID,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        deadline=date(2026, 5, 1),
        assignee="Alice",
        calendar_event_id=None,
    )
    new = _make_task(
        tid=_TASK_2_ID,
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        deadline=date(2026, 6, 1),
        assignee="Bob",
    )
    conflict = _merge_conflict_with_tasks(task_ids=[_TASK_2_ID, _TASK_ID])
    db = _FakeDB(tasks=[old, new], conflicts=[conflict])
    client = TestClient(_build_app(db, user))

    r = client.post(f"/tasks/conflicts/{_CONFLICT_ID}/merge", json={"fields": ["deadline", "assignee"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["merged_task_id"] == str(_TASK_ID)  # older survives
    assert body["dismissed_task_id"] == str(_TASK_2_ID)
    assert body["calendar_sync"]["status"] == "skipped"
    assert body["calendar_sync"]["reason"] == "no_calendar_event"
    # ORM objects were mutated in place
    assert old.deadline == date(2026, 6, 1)
    assert old.assignee == "Bob"
    assert old.previous_revision is not None and old.previous_revision["deadline"] == "2026-05-01"
    assert new.status == "dismissed"
    assert conflict.resolved is True


def test_merge_rejects_non_thread_update_scope() -> None:
    user = _make_user()
    old = _make_task(tid=_TASK_ID, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    new = _make_task(tid=_TASK_2_ID, created_at=datetime(2026, 4, 10, tzinfo=timezone.utc))
    conflict = _merge_conflict_with_tasks(scope="multi_source")
    db = _FakeDB(tasks=[old, new], conflicts=[conflict])
    client = TestClient(_build_app(db, user))
    r = client.post(f"/tasks/conflicts/{_CONFLICT_ID}/merge", json={"fields": ["deadline"]})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MERGE_SCOPE_UNSUPPORTED"


def test_merge_rejects_missing_task_ids() -> None:
    user = _make_user()
    conflict = _merge_conflict_with_tasks(task_ids=[_TASK_ID])  # only one task
    db = _FakeDB(tasks=[], conflicts=[conflict])
    client = TestClient(_build_app(db, user))
    r = client.post(f"/tasks/conflicts/{_CONFLICT_ID}/merge", json={"fields": ["deadline"]})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MERGE_MISSING_TASKS"


def test_merge_rejects_unmergeable_field() -> None:
    user = _make_user()
    conflict = _merge_conflict_with_tasks()
    db = _FakeDB(tasks=[], conflicts=[conflict])
    client = TestClient(_build_app(db, user))
    r = client.post(f"/tasks/conflicts/{_CONFLICT_ID}/merge", json={"fields": ["status"]})
    assert r.status_code == 422  # schema validation rejects non-allowlisted field


def test_merge_with_calendar_event_but_no_token_returns_skipped() -> None:
    """Surviving task has a calendar event + deadline changes, but the user has
    no Google token ⇒ merge still succeeds, calendar_sync skipped/no_token,
    nothing enqueued (no Redis touched)."""
    user = _make_user()  # oauth_token defaults to None
    old = _make_task(
        tid=_TASK_ID,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        deadline=date(2026, 5, 1),
        calendar_event_id="evt-existing",
    )
    new = _make_task(
        tid=_TASK_2_ID,
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        deadline=date(2026, 6, 1),
    )
    conflict = _merge_conflict_with_tasks(task_ids=[_TASK_2_ID, _TASK_ID])
    db = _FakeDB(tasks=[old, new], conflicts=[conflict])
    client = TestClient(_build_app(db, user))
    r = client.post(f"/tasks/conflicts/{_CONFLICT_ID}/merge", json={"fields": ["deadline"]})
    assert r.status_code == 200, r.text
    cal = r.json()["calendar_sync"]
    assert cal["status"] == "skipped"
    assert cal["reason"] == "no_token"
    assert old.deadline == date(2026, 6, 1)  # merge applied regardless


# ── Phase 2.3 Commit 5 carry-over: source endpoints ────────────────────────────


def test_get_task_source_returns_excerpt() -> None:
    user = _make_user()
    doc_id = uuid.uuid4()
    task = _make_task(source_doc_id=doc_id)
    doc = _make_source_doc(doc_id=doc_id, raw_text="<b>Hello</b>  world")
    db = _FakeDB(tasks=[task], source_docs=[doc])
    client = TestClient(_build_app(db, user))
    r = client.get(f"/tasks/{_TASK_ID}/source")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_type"] == "gmail"
    assert body["source_ref"] == "msg-abc"
    assert body["excerpt"] == "Hello world"  # HTML stripped, whitespace collapsed


def test_get_source_by_ref_returns_excerpt() -> None:
    user = _make_user()
    doc = _make_source_doc(doc_id=uuid.uuid4(), source_ref="19d6ca4d63fa4be4", raw_text="Plain body")
    db = _FakeDB(source_docs=[doc])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/source-by-ref?ref=19d6ca4d63fa4be4")
    assert r.status_code == 200, r.text
    assert r.json()["source_ref"] == "19d6ca4d63fa4be4"
    assert r.json()["excerpt"] == "Plain body"


# ── Phase 7.3 Confirm Gates ────────────────────────────────────────────────────


def test_patch_confirm_with_deadline_enqueues_calendar() -> None:
    """Confirming a task that has a deadline must enqueue a calendar_resync job
    and commit before enqueuing so the agent reads the confirmed state."""
    user = _make_user()
    t1 = _make_task(deadline=date(2026, 6, 1))
    db = _FakeDB(tasks=[t1])

    mock_redis = AsyncMock()
    mock_redis.rpush = AsyncMock()

    async def _fake_build(u):
        return "access-token-123", MagicMock()

    with (
        patch("app.api.tasks.get_redis", AsyncMock(return_value=mock_redis)),
        patch("app.api.conflicts._build_calendar_resync_payload", _fake_build),
    ):
        client = TestClient(_build_app(db, user))
        r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert db.committed is True
    mock_redis.rpush.assert_awaited_once()
    payload = json.loads(mock_redis.rpush.call_args[0][1])
    assert payload["source_type"] == "calendar_resync"
    assert payload["triggered_by"] == "task_confirm"
    assert payload["task_id"] == str(_TASK_ID)


def test_patch_confirm_no_deadline_skips_calendar() -> None:
    """Confirming a task with no deadline must not touch Redis — calendar events
    require a deadline to be meaningful."""
    user = _make_user()
    t1 = _make_task(deadline=None)
    db = _FakeDB(tasks=[t1])

    mock_redis = AsyncMock()

    with patch("app.api.tasks.get_redis", mock_redis):
        client = TestClient(_build_app(db, user))
        r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    mock_redis.assert_not_awaited()


def test_patch_dismissed_skips_calendar() -> None:
    """Dismissing a task must never trigger a calendar job."""
    user = _make_user()
    t1 = _make_task(deadline=date(2026, 6, 1))
    db = _FakeDB(tasks=[t1])

    mock_redis = AsyncMock()

    with patch("app.api.tasks.get_redis", mock_redis):
        client = TestClient(_build_app(db, user))
        r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "dismissed"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dismissed"
    mock_redis.assert_not_awaited()


def test_patch_confirm_no_google_token_still_succeeds() -> None:
    """When the user has no Google token the update still succeeds — the
    calendar job is simply not enqueued and no error is raised."""
    user = _make_user()  # oauth_token=None by default
    t1 = _make_task(deadline=date(2026, 6, 1))
    db = _FakeDB(tasks=[t1])

    mock_redis = AsyncMock()

    async def _fake_build_no_token(u):
        return None, MagicMock()  # no token

    with (
        patch("app.api.tasks.get_redis", AsyncMock(return_value=mock_redis)),
        patch("app.api.conflicts._build_calendar_resync_payload", _fake_build_no_token),
    ):
        client = TestClient(_build_app(db, user))
        r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed"})

    assert r.status_code == 200, r.text
    mock_redis.rpush.assert_not_awaited()


# ── Phase 7.2 confirmed_by provenance ─────────────────────────────────────────


def test_patch_confirm_sets_confirmed_by_user() -> None:
    """Explicit PATCH status=confirmed must set confirmed_by='user' on the task."""
    user = _make_user()
    t1 = _make_task()
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed"})
    assert r.status_code == 200, r.text
    assert t1.confirmed_by == "user"
    assert r.json()["confirmed_by"] == "user"


def test_patch_revert_to_pending_clears_confirmed_by() -> None:
    """Reverting to pending must clear confirmed_by=NULL so the 'Updated' badge
    doesn't appear for a task the user intentionally sent back to review."""
    user = _make_user()
    t1 = _make_task(status="confirmed", confirmed_by="system")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "pending"})
    assert r.status_code == 200, r.text
    assert t1.confirmed_by is None
    assert r.json()["confirmed_by"] is None


def test_patch_dismiss_preserves_confirmed_by() -> None:
    """Dismissing an auto-confirmed task does not change confirmed_by — the
    provenance is still useful for audit even when the task is dismissed."""
    user = _make_user()
    t1 = _make_task(status="confirmed", confirmed_by="system")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "dismissed"})
    assert r.status_code == 200, r.text
    assert t1.confirmed_by == "system"


def test_task_response_includes_confirmed_by() -> None:
    """confirmed_by must flow through TaskResponse so the frontend can show the
    'Auto' chip and 'Revert' button."""
    user = _make_user()
    t1 = _make_task(status="confirmed", confirmed_by="system")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.get(f"/tasks/{_TASK_ID}")
    assert r.status_code == 200
    assert r.json()["confirmed_by"] == "system"


def test_patch_confirm_after_supersede_overwrites_confirmed_by() -> None:
    """Edge case: auto-confirm → pipeline supersede → Anna confirms the update.

    After supersede: status=pending, confirmed_by=system ('Updated' badge).
    Anna confirms → status=confirmed, confirmed_by='user' (badge gone, task owned).
    The PATCH status=confirmed path must overwrite confirmed_by regardless of
    the prior value so the provenance reflects the current human decision.
    """
    user = _make_user()
    # Post-supersede state: was auto-confirmed, pipeline reset to pending
    t1 = _make_task(status="pending", confirmed_by="system")
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.patch(f"/tasks/{_TASK_ID}", json={"status": "confirmed"})
    assert r.status_code == 200, r.text
    assert t1.confirmed_by == "user"
    assert r.json()["confirmed_by"] == "user"


# ─── Phase 8.2: Team View ───────────────────────────────────────────────────

def _today() -> date:
    return datetime.now(timezone.utc).date()


def test_team_view_groups_by_canonical_assignee() -> None:
    user = _make_user()
    # Two tasks for "Minh" (canonical), one for "Lan"; canonical wins over raw.
    t1 = _make_task(tid=uuid.uuid4(), assignee="Minh N.", assignee_canonical="Minh", deadline=None)
    t2 = _make_task(tid=uuid.uuid4(), assignee="minh", assignee_canonical="Minh", deadline=None)
    t3 = _make_task(tid=uuid.uuid4(), assignee="Lan", assignee_canonical="Lan", deadline=None)
    db = _FakeDB(tasks=[t1, t2, t3])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/team")
    assert r.status_code == 200, r.text
    data = r.json()
    by_name = {m["assignee"]: m for m in data["members"]}
    assert by_name["Minh"]["open"] == 2
    assert by_name["Lan"]["open"] == 1


def test_team_view_risk_flags() -> None:
    user = _make_user()
    today = _today()
    overdue = _make_task(tid=uuid.uuid4(), assignee_canonical="Minh", deadline=today - timedelta(days=2))
    soon = _make_task(tid=uuid.uuid4(), assignee_canonical="Minh", deadline=today + timedelta(days=3))
    far = _make_task(tid=uuid.uuid4(), assignee_canonical="Minh", deadline=today + timedelta(days=60))
    db = _FakeDB(tasks=[overdue, soon, far])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/team")
    assert r.status_code == 200, r.text
    m = next(x for x in r.json()["members"] if x["assignee"] == "Minh")
    assert m["overdue"] == 1
    assert m["due_this_week"] == 1
    assert m["open"] == 3


def test_team_view_in_conflict_flag() -> None:
    user = _make_user()
    t1 = _make_task(tid=_TASK_ID, assignee_canonical="Minh", deadline=None)
    # _make_conflict references _TASK_ID in task_ids, unresolved.
    db = _FakeDB(tasks=[t1], conflicts=[_make_conflict()])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/team")
    assert r.status_code == 200, r.text
    m = next(x for x in r.json()["members"] if x["assignee"] == "Minh")
    assert m["in_conflict"] == 1


def test_team_view_needs_review_and_excludes_dismissed() -> None:
    user = _make_user()
    pending = _make_task(tid=uuid.uuid4(), assignee_canonical="Lan", status="pending", confirmed_by=None, deadline=None)
    confirmed = _make_task(tid=uuid.uuid4(), assignee_canonical="Lan", status="confirmed", confirmed_by="user", deadline=None)
    dismissed = _make_task(tid=uuid.uuid4(), assignee_canonical="Lan", status="dismissed", deadline=None)
    db = _FakeDB(tasks=[pending, confirmed, dismissed])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/team")
    assert r.status_code == 200, r.text
    m = next(x for x in r.json()["members"] if x["assignee"] == "Lan")
    assert m["open"] == 2          # dismissed excluded
    assert m["pending"] == 1
    assert m["confirmed"] == 1
    assert m["needs_review"] == 1  # only the pending+null one


def test_team_view_unassigned_bucket() -> None:
    user = _make_user()
    t1 = _make_task(tid=uuid.uuid4(), assignee=None, assignee_canonical=None, deadline=None)
    db = _FakeDB(tasks=[t1])
    client = TestClient(_build_app(db, user))
    r = client.get("/tasks/team")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unassigned"]["assignee"] is None
    assert data["unassigned"]["open"] == 1
    assert all(m["assignee"] is not None for m in data["members"])
