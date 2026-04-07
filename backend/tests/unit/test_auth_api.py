from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.api.deps import get_current_user
from app.models.user import User


class _FakeResult:
    def __init__(self, user: User | None):
        self._user = user

    def scalar_one_or_none(self) -> User | None:
        return self._user


class _FakeDB:
    def __init__(self, user_for_query: User | None = None):
        self.user_for_query = user_for_query
        self.added_users: list[User] = []

    async def execute(self, _stmt):
        return _FakeResult(self.user_for_query)

    def add(self, user: User) -> None:
        self.added_users.append(user)
        self.user_for_query = user


def _build_test_app(fake_db: _FakeDB, current_user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_api.router, prefix="/auth")

    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[auth_api.get_db] = _override_get_db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return app


def test_auth_google_redirects_to_google_url(monkeypatch) -> None:
    monkeypatch.setattr(auth_api, "build_google_auth_url", lambda: "https://accounts.google.com/o/oauth2/v2/auth?x=1")
    app = _build_test_app(_FakeDB())
    client = TestClient(app)
    response = client.get("/auth/google", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")


def test_auth_callback_creates_user_and_returns_access_token(monkeypatch) -> None:
    fake_db = _FakeDB(user_for_query=None)
    app = _build_test_app(fake_db)
    client = TestClient(app)

    async def _fake_exchange(_code: str) -> dict:
        return {
            "tokens": {"access_token": "ga-token"},
            "userinfo": {"email": "new-user@example.com", "id": "google-123"},
        }

    monkeypatch.setattr(auth_api, "exchange_code_for_tokens", _fake_exchange)
    monkeypatch.setattr(auth_api, "encrypt_token", lambda _tokens: "encrypted-token")
    monkeypatch.setattr(auth_api, "create_jwt", lambda _user_id: "jwt-token")

    response = client.get("/auth/callback?code=test-code&as_json=true")
    assert response.status_code == 200
    assert response.json() == {"access_token": "jwt-token", "token_type": "bearer"}
    assert len(fake_db.added_users) == 1
    assert fake_db.added_users[0].email == "new-user@example.com"
    assert fake_db.added_users[0].oauth_token == "encrypted-token"


def test_auth_me_returns_current_user() -> None:
    current_user = User(id=uuid4(), email="me@example.com")
    app = _build_test_app(_FakeDB(user_for_query=current_user), current_user=current_user)
    client = TestClient(app)
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_auth_logout_clears_oauth_token() -> None:
    current_user = User(id=uuid4(), email="me@example.com", oauth_token="encrypted")
    fake_db = _FakeDB(user_for_query=current_user)
    app = _build_test_app(fake_db, current_user=current_user)
    client = TestClient(app)
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"
    assert current_user.oauth_token is None
