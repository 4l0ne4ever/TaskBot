"""Unit tests for the MCP 401 auth-streak detection + suspension logic
introduced in pass 7 (RC #19).

Background: production Redis ``obs:pipeline:errors`` showed 22 consecutive
Gmail/Drive 401s over 3 days for the same user while the scheduler kept
firing every 15 minutes. OAuth refresh was silently succeeding (new access
token issued by Google) but the token no longer had valid scope — likely the
user revoked consent in their Google account. Blind retry wasted MCP/Groq
budget and produced no user-visible signal.

The fix tracks a per-(user, source) 401 streak in Redis; when it crosses
``mcp_auth_revoke_streak_threshold`` consecutive failures the consumer:

1. Writes a time-bounded ``sync:disabled:<uid>:<src>`` flag so subsequent
   jobs short-circuit without calling MCP.
2. Emits a distinct ``source_type="mcp_auth_revoked"`` pipeline error so
   dashboards / the frontend can surface a "reconnect Google" banner.

The success path clears the streak. Re-auth (in ``backend.auth``) also
clears both keys so the user isn't stuck until TTL expiry.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


class _FakeRedis:
    """Tiny in-memory Redis stub covering INCR / GET / SET / DEL / EXPIRE
    with enough semantics for the auth-streak path. We intentionally don't
    simulate TTL expiry — the tests assert the shape of writes, not time
    behaviour (TTL passing is covered by the real client)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.expiries: dict[str, int] = {}
        self.deleted: list[str] = []

    async def incr(self, key: str) -> int:
        cur = int(self.store.get(key, 0)) + 1
        self.store[key] = cur
        return cur

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self.store:
            return False
        self.expiries[key] = int(seconds)
        return True

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self.store[key] = value
        if ex is not None:
            self.expiries[key] = int(ex)
        return True

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
            self.deleted.append(k)
        return n


@pytest.fixture
def auth_mod(monkeypatch: pytest.MonkeyPatch):
    import importlib

    return importlib.import_module("app.scheduler.auth")


def _install(monkeypatch: pytest.MonkeyPatch, module, fake: _FakeRedis) -> None:
    async def _fake_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(module, "get_redis", _fake_redis)


def test_is_auth_revoked_error_recognizes_401_variants(auth_mod):
    m = auth_mod.is_auth_revoked_error
    assert m("MCP call failed [401]: {'detail': 'Invalid Credentials'}") is True
    assert m("oauth error: invalid_grant") is True
    assert m("HTTP 401 Unauthorized") is True
    assert m("status: 401") is True
    assert m("token revoked by user") is True


def test_is_auth_revoked_error_ignores_other_failures(auth_mod):
    m = auth_mod.is_auth_revoked_error
    assert m("MCP call failed [500]: Internal Server Error") is False
    assert m("pipeline daily quota (TPD) hit") is False
    assert m("timeout after 30s") is False
    assert m("") is False


def test_streak_increments_and_disables_at_threshold(auth_mod, monkeypatch):
    fake = _FakeRedis()
    _install(monkeypatch, auth_mod, fake)
    # Force threshold=3 so we don't drift when the default changes.
    monkeypatch.setattr(
        auth_mod.settings, "mcp_auth_revoke_streak_threshold", 3
    )
    monkeypatch.setattr(
        auth_mod.settings, "mcp_auth_revoke_disable_ttl_seconds", 3600
    )

    async def _run():
        s1, d1 = await auth_mod.record_mcp_auth_outcome(
            "u1", "gmail", auth_error=True
        )
        s2, d2 = await auth_mod.record_mcp_auth_outcome(
            "u1", "gmail", auth_error=True
        )
        s3, d3 = await auth_mod.record_mcp_auth_outcome(
            "u1", "gmail", auth_error=True
        )
        return (s1, d1), (s2, d2), (s3, d3)

    (s1, d1), (s2, d2), (s3, d3) = asyncio.run(_run())
    assert (s1, s2, s3) == (1, 2, 3)
    assert d1 is False and d2 is False
    assert d3 is True
    assert fake.store.get("sync:disabled:u1:gmail"), (
        "threshold breach must persist a suspend flag"
    )


def test_success_path_clears_streak(auth_mod, monkeypatch):
    fake = _FakeRedis()
    fake.store["mcp:auth_streak:u1:gmail"] = 2
    _install(monkeypatch, auth_mod, fake)

    async def _run():
        return await auth_mod.record_mcp_auth_outcome(
            "u1", "gmail", auth_error=False
        )

    streak, disabled = asyncio.run(_run())
    assert streak == 0 and disabled is False
    assert "mcp:auth_streak:u1:gmail" not in fake.store


def test_gmail_and_drive_streaks_are_independent(auth_mod, monkeypatch):
    fake = _FakeRedis()
    _install(monkeypatch, auth_mod, fake)
    monkeypatch.setattr(auth_mod.settings, "mcp_auth_revoke_streak_threshold", 2)

    async def _run():
        await auth_mod.record_mcp_auth_outcome("u1", "gmail", auth_error=True)
        await auth_mod.record_mcp_auth_outcome("u1", "gmail", auth_error=True)
        # drive should still be 0 — Google can revoke one scope without the other
        return await auth_mod.is_sync_disabled_for_auth("u1", "drive")

    disabled_drive = asyncio.run(_run())
    assert disabled_drive is None
    assert fake.store.get("sync:disabled:u1:gmail")


def test_flag_user_auth_revoked_emits_distinct_pipeline_error(
    auth_mod, monkeypatch
):
    fake = _FakeRedis()
    _install(monkeypatch, auth_mod, fake)
    monkeypatch.setattr(auth_mod.settings, "mcp_auth_revoke_streak_threshold", 1)

    captured: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(auth_mod, "record_pipeline_error", _capture)

    asyncio.run(
        auth_mod.flag_user_auth_revoked(
            "u1", "gmail", "MCP call failed [401]: Invalid Credentials"
        )
    )

    assert len(captured) == 1
    assert captured[0]["source_type"] == "mcp_auth_revoked"
    assert captured[0]["user_id"] == "u1"
    assert "streak=1" in captured[0]["error"]
