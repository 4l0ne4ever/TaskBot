"""Unit tests for the ``calendar_resync`` job handler (Phase 2.3 Commit 6).

After a thread_update conflict merge, the backend enqueues a
``{source_type: "calendar_resync", user_id, access_token, task_id}`` job. The
agent handler reuses the idempotent ``async_dispatch_notifications`` (which
calls ``update_event`` when the task already has a calendar_event_id) and adds
in-handler bounded retry for transient MCP/network blips. Auth-class failures
(401 / invalid_grant / 403) are user-actionable and must NOT be retried.
"""
from __future__ import annotations

import asyncio

import pytest

from app.scheduler import queue_consumer as qc

_TASK_ID = "11111111-1111-1111-1111-111111111111"
_USER_ID = "22222222-2222-2222-2222-222222222222"


def _patch_no_sleep(monkeypatch) -> None:
    async def _instant(_seconds):
        return None

    monkeypatch.setattr(qc.asyncio, "sleep", _instant)


def test_calendar_resync_success_first_attempt(monkeypatch) -> None:
    calls = {"dispatch": 0, "errors": []}

    async def _ok(state):
        calls["dispatch"] += 1
        return {"notifications_sent": [{"task_id": state["saved_task_ids"][0]}], "errors": []}

    monkeypatch.setattr("app.services.notification_service.async_dispatch_notifications", _ok)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))
    _patch_no_sleep(monkeypatch)

    asyncio.run(qc._process_calendar_resync_job(_USER_ID, "tok", _TASK_ID))

    assert calls["dispatch"] == 1
    assert calls["errors"] == []  # no permanent-failure record


def test_calendar_resync_retries_transient_then_succeeds(monkeypatch) -> None:
    calls = {"dispatch": 0, "errors": []}

    async def _flaky(state):
        calls["dispatch"] += 1
        if calls["dispatch"] == 1:
            # transient: a non-auth error mentioning the task id
            return {"notifications_sent": [], "errors": [f"dispatch_notifications failed for task {_TASK_ID}: connection reset"]}
        return {"notifications_sent": [{"task_id": _TASK_ID}], "errors": []}

    monkeypatch.setattr("app.services.notification_service.async_dispatch_notifications", _flaky)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))
    _patch_no_sleep(monkeypatch)

    asyncio.run(qc._process_calendar_resync_job(_USER_ID, "tok", _TASK_ID))

    assert calls["dispatch"] == 2  # retried once, then succeeded
    assert calls["errors"] == []


def test_calendar_resync_auth_revoked_no_retry(monkeypatch) -> None:
    calls = {"dispatch": 0, "errors": []}

    async def _auth_fail(state):
        calls["dispatch"] += 1
        return {"notifications_sent": [], "errors": [f"dispatch_notifications failed for task {_TASK_ID}: MCP call failed [401] invalid_grant"]}

    monkeypatch.setattr("app.services.notification_service.async_dispatch_notifications", _auth_fail)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))
    _patch_no_sleep(monkeypatch)

    asyncio.run(qc._process_calendar_resync_job(_USER_ID, "tok", _TASK_ID))

    assert calls["dispatch"] == 1  # permanent — not retried
    assert len(calls["errors"]) == 1
    assert calls["errors"][0]["source_type"] == "calendar_resync"


def test_calendar_resync_exhausts_retries_records_error(monkeypatch) -> None:
    calls = {"dispatch": 0, "errors": []}

    async def _always_transient(state):
        calls["dispatch"] += 1
        return {"notifications_sent": [], "errors": [f"dispatch_notifications failed for task {_TASK_ID}: timeout"]}

    monkeypatch.setattr("app.services.notification_service.async_dispatch_notifications", _always_transient)
    monkeypatch.setattr(qc, "record_pipeline_error", lambda **k: calls["errors"].append(k))
    _patch_no_sleep(monkeypatch)

    asyncio.run(qc._process_calendar_resync_job(_USER_ID, "tok", _TASK_ID))

    assert calls["dispatch"] == qc._CALENDAR_RESYNC_MAX_ATTEMPTS
    assert len(calls["errors"]) == 1
    assert "exhausted" in calls["errors"][0]["error"]
