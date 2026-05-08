import json

import httpx
import pytest

from app.scheduler.jobs import (
    _refresh_access_token,
    sync_all_users_drive,
    sync_all_users_gmail,
)


@pytest.mark.asyncio
async def test_sync_all_users_gmail_enqueues_each_user(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _users():
        return [
            {"id": "u1", "access_token": "t1", "sync_profile": "balanced"},
            {"id": "u2", "access_token": "t2", "sync_profile": "balanced"},
        ]

    pushed: list[tuple[str, str]] = []

    class _FakeRedis:
        async def rpush(self, name: str, job: str) -> None:
            pushed.append((name, job))

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("app.scheduler.jobs._get_sync_eligible_users", _users)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_k: _FakeRedis())

    await sync_all_users_gmail()
    assert len(pushed) == 2
    for _q, job in pushed:
        j = json.loads(job)
        assert j["source_type"] == "gmail"
        assert j["triggered_by"] == "auto"


@pytest.mark.asyncio
async def test_sync_all_users_drive_enqueues_when_users_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _users():
        return [{"id": "u2", "access_token": "t2", "sync_profile": "balanced"}]

    pushed: list[str] = []

    class _FakeRedis:
        async def rpush(self, name: str, job: str) -> None:
            pushed.append(job)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("app.scheduler.jobs._get_sync_eligible_users", _users)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_k: _FakeRedis())

    await sync_all_users_drive()
    assert len(pushed) == 1
    assert json.loads(pushed[0])["source_type"] == "drive"


class _StubAsyncClient:
    def __init__(self, *, status_code: int, payload: dict | None = None, exc: Exception | None = None):
        self._status = status_code
        self._payload = payload or {}
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return self

    async def __aexit__(self, *_a):
        return False

    async def post(self, *_a, **_k):
        return httpx.Response(
            status_code=self._status,
            text=json.dumps(self._payload),
            request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
        )


@pytest.mark.asyncio
async def test_refresh_access_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubAsyncClient(
        status_code=200,
        payload={"access_token": "new-at", "expires_in": 3600, "token_type": "Bearer"},
    )
    monkeypatch.setattr("app.scheduler.jobs.httpx.AsyncClient", lambda *a, **k: stub)
    data, err = await _refresh_access_token("refresh-abc")
    assert err is None
    assert data is not None and data["access_token"] == "new-at"


@pytest.mark.asyncio
async def test_refresh_access_token_http_error_surfaces_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubAsyncClient(status_code=400, payload={"error": "invalid_grant"})
    monkeypatch.setattr("app.scheduler.jobs.httpx.AsyncClient", lambda *a, **k: stub)
    data, err = await _refresh_access_token("revoked")
    assert data is None
    assert err is not None
    assert err.startswith("http_400")


@pytest.mark.asyncio
async def test_refresh_access_token_transport_error_surfaces_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubAsyncClient(status_code=0, exc=httpx.ConnectError("dns fail"))
    monkeypatch.setattr("app.scheduler.jobs.httpx.AsyncClient", lambda *a, **k: stub)
    data, err = await _refresh_access_token("abc")
    assert data is None
    assert err is not None and err.startswith("transport:")


@pytest.mark.asyncio
async def test_refresh_access_token_missing_access_token_surfaces_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubAsyncClient(status_code=200, payload={"token_type": "Bearer"})
    monkeypatch.setattr("app.scheduler.jobs.httpx.AsyncClient", lambda *a, **k: stub)
    data, err = await _refresh_access_token("abc")
    assert data is None
    assert err == "invalid_response:no_access_token"
