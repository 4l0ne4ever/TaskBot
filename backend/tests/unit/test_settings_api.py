import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.api.deps import get_current_user
from app.models.user import User

_USER_ID = uuid.uuid4()


def _make_user(**overrides) -> User:
    defaults = {
        "id": _USER_ID,
        "email": "test@example.com",
        "oauth_token": "encrypted",
        "sync_config": {"gmail_interval": 15, "drive_interval": 30},
    }
    defaults.update(overrides)
    return User(**defaults)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, one=None):
        self._one = one

    def scalar_one_or_none(self):
        return self._one


class _FakeDB:
    def __init__(self, user: User | None = None):
        self._user = user

    async def execute(self, _stmt):
        return _FakeResult(one=self._user)

    async def commit(self):
        pass

    async def rollback(self):
        pass


def _build_app(fake_db: _FakeDB, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(settings_api.router, prefix="/settings")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[settings_api.get_db] = _override_get_db
    if user:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def test_get_settings_returns_current_config() -> None:
    user = _make_user()
    db = _FakeDB(user)
    client = TestClient(_build_app(db, user))
    r = client.get("/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["gmail_interval"] == 15
    assert data["drive_interval"] == 30
    assert data["google_connected"] is True


def test_get_settings_disconnected_user() -> None:
    user = _make_user(oauth_token=None)
    db = _FakeDB(user)
    client = TestClient(_build_app(db, user))
    r = client.get("/settings")
    assert r.status_code == 200
    assert r.json()["google_connected"] is False


def test_patch_settings_updates_intervals() -> None:
    user = _make_user()
    db = _FakeDB(user)
    client = TestClient(_build_app(db, user))
    r = client.patch("/settings", json={"gmail_interval": 10})
    assert r.status_code == 200
    assert r.json()["gmail_interval"] == 10


def test_disconnect_google_clears_token() -> None:
    user = _make_user()
    db = _FakeDB(user)
    client = TestClient(_build_app(db, user))
    r = client.post("/settings/disconnect")
    assert r.status_code == 200
    assert r.json()["message"] == "Google account disconnected"
    assert user.oauth_token is None


def test_disconnect_already_disconnected() -> None:
    user = _make_user(oauth_token=None)
    db = _FakeDB(user)
    client = TestClient(_build_app(db, user))
    r = client.post("/settings/disconnect")
    assert r.status_code == 200
    assert r.json()["message"] == "Already disconnected"
