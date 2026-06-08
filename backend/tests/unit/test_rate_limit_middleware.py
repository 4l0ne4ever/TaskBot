"""Rate limiter exemption tests (2026-06-07).

The Sync page polls ``/sync/status`` and ``/sync/progress`` every 2s. With the
60 req/60s global limit those two endpoints alone burn the budget in ~40s,
even before the rest of the app sends a single request. Both are O(1) Redis
lookups so the cost protection isn't needed — the frontend's setInterval is
the real throttle. Exempt them.

These tests assert the exemption set is what the deployed behavior depends
on; if someone removes an entry, the Sync UI starts 429'ing under normal use.
"""
from __future__ import annotations

import asyncio

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware import RateLimitMiddleware, _EXEMPT_PATHS


def _ok(_request):
    return PlainTextResponse("ok")


def _build_app(limit: int = 3, window: int = 60) -> TestClient:
    """Tiny app with a few paths covering the exemption surface."""
    app = Starlette(routes=[
        Route("/health", _ok),
        Route("/sync/status", _ok),
        Route("/sync/progress", _ok),
        Route("/tasks", _ok),
    ])
    app.add_middleware(RateLimitMiddleware, limit=limit, window=window)
    return TestClient(app)


def test_exempt_paths_set_includes_polling_endpoints():
    """Lock the set — these are the entries the Sync UI relies on."""
    assert "/sync/status" in _EXEMPT_PATHS
    assert "/sync/progress" in _EXEMPT_PATHS
    assert "/health" in _EXEMPT_PATHS
    assert "/openapi.json" in _EXEMPT_PATHS


def test_non_exempt_path_returns_429_after_limit():
    """Sanity: the limiter still works for non-exempt endpoints — a real
    burst against /tasks gets 429 after the configured limit."""
    client = _build_app(limit=2)
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks").status_code == 429


def test_exempt_paths_never_429_even_past_limit():
    """The whole point of the exemption: a Sync page polling at 2s for an
    hour must never hit 429. Simulate by sending 10× the configured budget."""
    client = _build_app(limit=2)
    for _ in range(20):
        assert client.get("/sync/status").status_code == 200
        assert client.get("/sync/progress").status_code == 200


def test_exempt_polling_doesnt_consume_budget_for_other_endpoints():
    """An aggressive Sync page must not poison the user's budget on other
    endpoints. Burn 50 exempt polls, then verify /tasks still has its full
    budget. (Buckets are keyed per-user; exempt paths bypass before bucket
    increment, so they shouldn't show up at all.)"""
    client = _build_app(limit=2)
    for _ in range(50):
        client.get("/sync/status")
    # Budget intact: 2 successful /tasks, third 429s.
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks").status_code == 429
