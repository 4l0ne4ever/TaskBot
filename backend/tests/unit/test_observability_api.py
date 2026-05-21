import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import observability as obs_api
from app.api.deps import get_current_user
from app.models.pipeline_run import PipelineRun
from app.models.user import User

_USER_ID = uuid.uuid4()
_OTHER_USER_ID = uuid.uuid4()


def _make_user(**overrides) -> User:
    defaults = {"id": _USER_ID, "email": "obs@example.com", "oauth_token": "encrypted"}
    defaults.update(overrides)
    return User(**defaults)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return _FakeScalars(self._rows)

    def scalar_one(self):
        if not self._rows:
            return 0
        return self._rows[0]

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(
        self,
        *,
        pipeline_runs=None,
        total_by_doc=None,
        missing_by_doc=None,
        quality_rows=None,
        sync_states=None,
    ):
        self._pipeline_runs = pipeline_runs or []
        self._total_by_doc = total_by_doc or {}
        self._missing_by_doc = missing_by_doc or {}
        # quality_rows: list of (status, confirmed_by, count) tuples
        self._quality_rows = quality_rows or []
        self._sync_states = sync_states or []

    async def execute(self, stmt):
        text = str(stmt)
        if "FROM pipeline_runs" in text and "count(" in text and "status = :status_1" in text:
            failed = sum(1 for r in self._pipeline_runs if r.status == "failed")
            return _FakeResult(rows=[failed])
        if "FROM pipeline_runs" in text and "count(" in text:
            return _FakeResult(rows=[len(self._pipeline_runs)])
        if "FROM pipeline_runs" in text:
            return _FakeResult(rows=self._pipeline_runs)
        if "FROM sync_states" in text:
            return _FakeResult(rows=self._sync_states)
        if "FROM tasks" in text and "GROUP BY tasks.status" in text:
            return _FakeResult(rows=self._quality_rows)
        if "FROM tasks" in text and "GROUP BY tasks.source_doc_id" in text:
            if "tasks.deadline IS NULL" in text:
                return _FakeResult(rows=list(self._missing_by_doc.items()))
            return _FakeResult(rows=list(self._total_by_doc.items()))
        if "FROM tasks" in text and "tasks.deadline IS NULL" in text:
            return _FakeResult(rows=[sum(self._missing_by_doc.values())])
        if "FROM tasks" in text:
            return _FakeResult(rows=[sum(self._total_by_doc.values())])
        return _FakeResult(rows=[])


class _FakeRedis:
    def __init__(
        self,
        calls_rows=None,
        err_rows=None,
        langsmith_counts=None,
        langsmith_events=None,
    ):
        self._calls_rows = calls_rows or []
        self._err_rows = err_rows or []
        self._langsmith_counts = langsmith_counts or {}
        self._langsmith_events = langsmith_events or []

    async def hgetall(self, key):
        if key == "obs:langsmith:ingest:counts":
            return {k: str(v) for k, v in self._langsmith_counts.items()}
        return {}

    async def lrange(self, key, _start, _end):
        if key == "obs:llm:calls":
            return list(self._calls_rows)
        if key == "obs:pipeline:errors":
            return list(self._err_rows)
        if key == "obs:langsmith:ingest:events":
            return list(self._langsmith_events)
        return []


def _build_app(fake_db: _FakeDB, fake_redis: _FakeRedis, monkeypatch) -> FastAPI:
    app = FastAPI()
    app.include_router(obs_api.router, prefix="/observability")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[obs_api.get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    async def _get_fake_redis():
        return fake_redis

    monkeypatch.setattr(obs_api, "get_redis", _get_fake_redis)
    monkeypatch.setattr(obs_api.settings, "internal_observability_token", "secret-token")
    return app


def test_summary_filters_user_scoped_llm_rows(monkeypatch) -> None:
    fake_db = _FakeDB()
    fake_redis = _FakeRedis(
        calls_rows=[
            json.dumps({"user_id": str(_USER_ID), "latency_ms": 100, "total_tokens": 10, "cost_estimate": 0.1}),
            json.dumps({"user_id": str(_OTHER_USER_ID), "latency_ms": 900, "total_tokens": 999, "cost_estimate": 9.9}),
            json.dumps({"latency_ms": 50, "total_tokens": 5, "cost_estimate": 0.01}),
        ]
    )
    app = _build_app(fake_db, fake_redis, monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/summary", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    data = r.json()
    # Includes current user's row + legacy row without user_id, excludes other user's row.
    assert data["llm"]["sample_size"] == 2
    assert data["llm"]["total_tokens"] == 15


def test_summary_includes_langsmith_ingest_block(monkeypatch) -> None:
    fake_db = _FakeDB()
    ev = json.dumps(
        {"ts": "2026-04-27T00:00:00+00:00", "outcome": "http_error", "status_code": 429, "run_name": "x", "detail": ""}
    )
    fake_redis = _FakeRedis(
        langsmith_counts={"attempts": 10, "success": 7, "http_error": 3, "http_429": 3},
        langsmith_events=[ev],
    )
    app = _build_app(fake_db, fake_redis, monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/summary", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    ls = r.json()["langsmith_ingest"]
    assert ls["counts"]["attempts"] == 10
    assert ls["counts"]["http_429"] == 3
    assert ls["failure_rate"] == 0.3
    assert len(ls["recent_events"]) == 1
    assert ls["recent_events"][0]["status_code"] == 429


def test_runs_uses_grouped_task_counts(monkeypatch) -> None:
    doc1 = uuid.uuid4()
    doc2 = uuid.uuid4()
    run1 = PipelineRun(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        source_doc_id=doc1,
        status="completed",
        tasks_extracted=3,
        conflicts_found=0,
        started_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 1, 0, 2, tzinfo=timezone.utc),
    )
    run2 = PipelineRun(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        source_doc_id=doc2,
        status="failed",
        tasks_extracted=2,
        conflicts_found=1,
        started_at=datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 1, 1, 3, tzinfo=timezone.utc),
    )
    fake_db = _FakeDB(
        pipeline_runs=[run2, run1],
        total_by_doc={doc1: 3, doc2: 2},
        missing_by_doc={doc1: 1, doc2: 0},
    )
    fake_redis = _FakeRedis()
    app = _build_app(fake_db, fake_redis, monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/runs?limit=2", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["summary"]["count"] == 2
    assert payload["summary"]["error_rate"] == 0.5
    by_id = {row["pipeline_run_id"]: row for row in payload["runs"]}
    assert by_id[str(run1.id)]["quality"]["total_tasks"] == 3
    assert by_id[str(run1.id)]["quality"]["missing_deadline_tasks"] == 1
    assert by_id[str(run2.id)]["quality"]["total_tasks"] == 2
    assert by_id[str(run2.id)]["quality"]["missing_deadline_tasks"] == 0


def test_quality_funnel_and_auto_confirm_rate(monkeypatch) -> None:
    # 30 auto-confirmed, 3 manually confirmed, 5 need review, 2 superseded
    # (pending but previously confirmed), 1 dismissed → 41 total.
    fake_db = _FakeDB(
        quality_rows=[
            ("confirmed", "system", 30),
            ("confirmed", "user", 3),
            ("pending", None, 5),
            ("pending", "system", 2),
            ("dismissed", None, 1),
        ]
    )
    app = _build_app(fake_db, _FakeRedis(), monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/quality", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_tasks"] == 41
    assert data["by_status"] == {"confirmed": 33, "pending": 7, "dismissed": 1}
    assert data["by_confirmed_by"] == {"system": 32, "user": 3, "none": 6}
    ac = data["auto_confirm"]
    assert ac["system_confirmed"] == 32          # 30 confirmed + 2 superseded
    assert ac["currently_confirmed_auto"] == 30  # only status=confirmed
    assert ac["user_confirmed"] == 3
    assert ac["superseded"] == 2                 # pending + non-null confirmed_by
    assert ac["need_review"] == 5                # pending + null confirmed_by
    assert ac["auto_confirm_rate"] == round(32 / 41, 4)
    assert data["calibration"]["ece_offline_baseline"] == 0.108


def test_quality_empty_returns_zero_rate(monkeypatch) -> None:
    app = _build_app(_FakeDB(quality_rows=[]), _FakeRedis(), monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/quality", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_tasks"] == 0
    assert data["auto_confirm"]["auto_confirm_rate"] == 0.0


def test_sync_health_flags_stale_and_error(monkeypatch) -> None:
    from app.models.sync_state import SyncState

    now = datetime.now(timezone.utc)
    fresh = SyncState(
        id=uuid.uuid4(), user_id=_USER_ID, source_type="gmail",
        last_sync_at=now - timedelta(minutes=5), status="idle", error_message=None,
    )
    stale = SyncState(
        id=uuid.uuid4(), user_id=_USER_ID, source_type="drive",
        last_sync_at=now - timedelta(minutes=120), status="idle", error_message=None,
    )
    fake_db = _FakeDB(sync_states=[fresh, stale])
    app = _build_app(fake_db, _FakeRedis(), monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/sync-health", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    data = r.json()
    by_source = {s["source_type"]: s for s in data["sources"]}
    # gmail interval 15 → 5min is fresh; drive interval 30 → 120min > 2x60 stale.
    assert by_source["gmail"]["is_stale"] is False
    assert by_source["drive"]["is_stale"] is True
    assert data["overall"] == "stale"


def test_sync_health_never_synced_is_stale(monkeypatch) -> None:
    from app.models.sync_state import SyncState

    never = SyncState(
        id=uuid.uuid4(), user_id=_USER_ID, source_type="gmail",
        last_sync_at=None, status="error", error_message="token expired",
    )
    fake_db = _FakeDB(sync_states=[never])
    app = _build_app(fake_db, _FakeRedis(), monkeypatch)
    client = TestClient(app)
    r = client.get("/observability/sync-health", headers={"x-internal-token": "secret-token"})
    assert r.status_code == 200, r.text
    data = r.json()
    src = data["sources"][0]
    assert src["is_stale"] is True
    assert src["staleness_minutes"] is None
    assert src["has_error"] is True
    assert data["overall"] == "error"
