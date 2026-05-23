"""Unit tests for the ``weekly_brief`` job handler (Phase 8.3).

The backend (manual) and APScheduler (cron) both enqueue
``{source_type: "weekly_brief", user_id, access_token}``. The handler delegates
to ``async_send_weekly_brief`` and, on failure (e.g. missing gmail.send scope →
403), records a user-actionable pipeline error rather than raising.
"""
from __future__ import annotations

import asyncio

from app.scheduler import queue_consumer as qc

_USER_ID = "22222222-2222-2222-2222-222222222222"


def test_weekly_brief_success_records_no_error(monkeypatch) -> None:
    calls = {"errors": []}

    async def _sent(user_id, access_token):
        assert user_id == _USER_ID
        assert access_token == "tok"
        return {"sent": True, "errors": [], "data": {}}

    monkeypatch.setattr("app.services.weekly_brief_service.async_send_weekly_brief", _sent)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))

    asyncio.run(qc._process_weekly_brief_job(_USER_ID, "tok"))
    assert calls["errors"] == []


def test_weekly_brief_failure_records_error(monkeypatch) -> None:
    calls = {"errors": []}

    async def _failed(user_id, access_token):
        return {"sent": False, "errors": ["weekly_brief send failed: [403] insufficient scope"], "data": {}}

    monkeypatch.setattr("app.services.weekly_brief_service.async_send_weekly_brief", _failed)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))

    asyncio.run(qc._process_weekly_brief_job(_USER_ID, "tok"))
    assert len(calls["errors"]) == 1
    rec = calls["errors"][0]
    assert rec["source_type"] == "weekly_brief"
    assert "403" in rec["error"]
