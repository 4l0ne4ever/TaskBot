import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import sync as sync_api
from app.api.deps import get_current_user
from app.models.pipeline_run import PipelineRun
from app.models.sync_state import SyncState
from app.models.user import User

_USER_ID = uuid.uuid4()


def _make_user(**overrides) -> User:
    defaults = {"id": _USER_ID, "email": "test@example.com", "oauth_token": "encrypted"}
    defaults.update(overrides)
    return User(**defaults)


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
    def __init__(self, sync_states=None, pipeline_runs=None):
        self._sync_states = sync_states or []
        self._pipeline_runs = pipeline_runs or []

    async def execute(self, stmt):
        stmt_str = str(stmt)
        if "pipeline_runs" in stmt_str:
            return _FakeResult(rows=self._pipeline_runs)
        if "sync_states" in stmt_str:
            return _FakeResult(rows=self._sync_states, one=self._sync_states[0] if self._sync_states else None)
        return _FakeResult()

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _FakeRedis:
    def __init__(self):
        self.queue: list[str] = []

    async def rpush(self, key, value):
        self.queue.append(value)


def _build_app(
    fake_db: _FakeDB,
    user: User | None = None,
    fake_redis=None,
    monkeypatch=None,
    *,
    patch_decrypt: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(sync_api.router, prefix="/sync")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[sync_api.get_db] = _override_get_db
    if user:
        app.dependency_overrides[get_current_user] = lambda: user

    if monkeypatch and fake_redis:
        async def _get_fake_redis():
            return fake_redis

        monkeypatch.setattr(sync_api, "get_redis", _get_fake_redis)
        if patch_decrypt:
            monkeypatch.setattr(sync_api, "decrypt_token", lambda _t: {"access_token": "ga-token"})

    return app


def test_sync_status_returns_states() -> None:
    user = _make_user()
    s1 = SyncState(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        source_type="gmail",
        last_sync_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        status="idle",
    )
    db = _FakeDB(sync_states=[s1])
    client = TestClient(_build_app(db, user))
    r = client.get("/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["source_type"] == "gmail"


def test_sync_trigger_enqueues_job(monkeypatch) -> None:
    user = _make_user()
    redis = _FakeRedis()
    db = _FakeDB(sync_states=[])
    client = TestClient(_build_app(db, user, fake_redis=redis, monkeypatch=monkeypatch))
    r = client.post("/sync/trigger?source=gmail")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert len(redis.queue) == 1


def test_sync_trigger_rejects_without_google_token() -> None:
    user = _make_user(oauth_token=None)
    db = _FakeDB()
    client = TestClient(_build_app(db, user))
    r = client.post("/sync/trigger?source=gmail")
    assert r.status_code == 400


def test_sync_trigger_refreshes_access_token_before_enqueue(monkeypatch) -> None:
    user = _make_user()
    redis = _FakeRedis()
    db = _FakeDB(sync_states=[])
    monkeypatch.setattr(
        sync_api,
        "decrypt_token",
        lambda _t: {"access_token": "stale-token", "refresh_token": "r1"},
    )
    async def _refresh(_refresh_token: str):
        return {"access_token": "fresh-token", "expires_in": 3600}, None
    monkeypatch.setattr(sync_api, "refresh_google_access_token", _refresh)
    monkeypatch.setattr(sync_api, "encrypt_token", lambda tok: f"enc::{tok.get('access_token')}")
    client = TestClient(_build_app(db, user, fake_redis=redis, monkeypatch=monkeypatch, patch_decrypt=False))
    r = client.post("/sync/trigger?source=gmail")
    assert r.status_code == 200
    assert len(redis.queue) == 1
    payload = json.loads(redis.queue[0])
    assert payload["access_token"] == "fresh-token"
    assert user.oauth_token == "enc::fresh-token"


def test_sync_trigger_returns_401_when_refresh_fails(monkeypatch) -> None:
    user = _make_user()
    redis = _FakeRedis()
    db = _FakeDB(sync_states=[])
    monkeypatch.setattr(
        sync_api,
        "decrypt_token",
        lambda _t: {"access_token": "stale-token", "refresh_token": "r1"},
    )
    async def _refresh(_refresh_token: str):
        return None, "http_400:invalid_grant"
    monkeypatch.setattr(sync_api, "refresh_google_access_token", _refresh)
    client = TestClient(_build_app(db, user, fake_redis=redis, monkeypatch=monkeypatch, patch_decrypt=False))
    r = client.post("/sync/trigger?source=gmail")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "GOOGLE_AUTH_EXPIRED"
    assert len(redis.queue) == 0


def test_sync_trigger_returns_400_when_stored_token_invalid(monkeypatch) -> None:
    user = _make_user()
    redis = _FakeRedis()
    db = _FakeDB(sync_states=[])
    def _broken_decrypt(_token):
        raise ValueError("broken")
    monkeypatch.setattr(sync_api, "decrypt_token", _broken_decrypt)
    client = TestClient(_build_app(db, user, fake_redis=redis, monkeypatch=monkeypatch, patch_decrypt=False))
    r = client.post("/sync/trigger?source=gmail")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_GOOGLE_TOKEN"
    assert len(redis.queue) == 0


def test_sync_history_returns_pipeline_runs() -> None:
    user = _make_user()
    run = PipelineRun(
        id=uuid.uuid4(),
        user_id=_USER_ID,
        status="completed",
        tasks_extracted=3,
        conflicts_found=0,
        started_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 1, 0, 5, tzinfo=timezone.utc),
    )
    db = _FakeDB(pipeline_runs=[run])
    client = TestClient(_build_app(db, user))
    r = client.get("/sync/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["tasks_extracted"] == 3
