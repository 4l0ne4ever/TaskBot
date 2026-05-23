"""Unit tests for the Weekly Brief manual trigger (Phase 8.3, POST /digest/send)."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import digest as digest_api
from app.api.deps import get_current_user
from app.models.user import User

_USER_ID = uuid.uuid4()


def _make_user() -> User:
    return User(id=_USER_ID, email="anna@example.com", oauth_token="enc")


class _FakeDB:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


class _FakeRedis:
    def __init__(self):
        self.pushed: list = []

    async def rpush(self, queue, payload):
        self.pushed.append((queue, payload))
        return 1


def _build_app(fake_db, fake_redis, monkeypatch, *, token, info_reason=None):
    app = FastAPI()
    app.include_router(digest_api.router, prefix="/digest")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[digest_api.get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user()

    async def _get_fake_redis():
        return fake_redis

    monkeypatch.setattr(digest_api, "get_redis", _get_fake_redis)

    # _build_calendar_resync_payload is imported inside the handler from
    # app.api.conflicts — patch it there.
    from types import SimpleNamespace

    async def _fake_payload(user):
        return token, SimpleNamespace(reason=info_reason, status="x", message="m")

    monkeypatch.setattr("app.api.conflicts._build_calendar_resync_payload", _fake_payload)
    return app


def test_send_queues_job_when_token_available(monkeypatch) -> None:
    db, redis = _FakeDB(), _FakeRedis()
    app = _build_app(db, redis, monkeypatch, token="access-tok")
    client = TestClient(app)
    r = client.post("/digest/send")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued"
    assert db.committed is True
    assert len(redis.pushed) == 1
    import json

    _, payload = redis.pushed[0]
    job = json.loads(payload)
    assert job["source_type"] == "weekly_brief"
    assert job["access_token"] == "access-tok"
    assert job["user_id"] == str(_USER_ID)


def test_send_skipped_when_no_token(monkeypatch) -> None:
    db, redis = _FakeDB(), _FakeRedis()
    app = _build_app(db, redis, monkeypatch, token=None, info_reason="token_expired")
    client = TestClient(app)
    r = client.post("/digest/send")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "skipped"
    assert body["reason"] == "token_expired"
    assert redis.pushed == []  # nothing enqueued
