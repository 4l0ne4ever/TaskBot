"""Unit tests for the ``daily_digest`` queue handler (Round 9, 2026-05-30).

Sibling of ``test_queue_consumer_weekly_brief.py`` — same fail-safe contract:
a missing gmail.send scope yields a 403 which ``async_send_daily_digest``
returns as an error rather than raising. The handler records it via
``record_pipeline_error`` and does NOT re-raise (kept silent at the
queue-consumer level so one bad user doesn't poison the loop).
"""
from __future__ import annotations

import asyncio

from app.scheduler.processors import daily_digest as dd

_USER_ID = "22222222-2222-2222-2222-222222222222"


def test_daily_digest_success_records_no_error(monkeypatch) -> None:
    calls = {"errors": []}

    async def _sent(user_id, access_token):
        assert user_id == _USER_ID
        assert access_token == "tok"
        return {"sent": True, "errors": [], "data": {}}

    monkeypatch.setattr("app.services.daily_digest_service.async_send_daily_digest", _sent)
    monkeypatch.setattr(dd, "record_pipeline_error", lambda **k: calls["errors"].append(k))

    asyncio.run(dd.process_daily_digest_job(_USER_ID, "tok"))
    assert calls["errors"] == []


def test_daily_digest_failure_records_user_actionable_error(monkeypatch) -> None:
    calls = {"errors": []}

    async def _failed(user_id, access_token):
        return {
            "sent": False,
            "errors": ["daily_digest send failed: [403] insufficient scope"],
            "data": {},
        }

    monkeypatch.setattr("app.services.daily_digest_service.async_send_daily_digest", _failed)
    monkeypatch.setattr(dd, "record_pipeline_error", lambda **k: calls["errors"].append(k))

    asyncio.run(dd.process_daily_digest_job(_USER_ID, "tok"))
    assert len(calls["errors"]) == 1
    rec = calls["errors"][0]
    assert rec["source_type"] == "daily_digest"
    assert "403" in rec["error"]
