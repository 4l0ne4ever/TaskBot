"""Tests for the Google Calendar REST v3 client (post-MCP-pivot, 2026-05-30).

Covered:

- ``create_event`` POSTs to the right URL with the bearer header, sends an
  all-day body with start=date and end=date+1 (Google's exclusive-end rule),
  optional description omitted when not provided.
- ``update_event`` PATCHes the event-id URL with the same body shape and
  returns the preserved ``event_id``.
- ``_raise_for_status`` formats a ``RuntimeError`` whose message contains
  the status code in ``[NNN]`` form, so ``notification_service``'s
  ``"403" in str(exc)`` detector and ``_process_calendar_resync_job``'s
  auth-revoked detector both keep working.
- Date-arithmetic edge: month/year boundary on the end-exclusive date.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.mcp.calendar_client import (
    _CALENDAR_EVENTS_URL,
    CalendarMCPClient,
)


def _mock_response(status: int, payload: dict | None = None, text: str = "") -> httpx.Response:
    req = httpx.Request("POST", _CALENDAR_EVENTS_URL)
    if payload is not None:
        return httpx.Response(status, request=req, content=json.dumps(payload).encode())
    return httpx.Response(status, request=req, content=text.encode())


@pytest.fixture
def fake_http_client(monkeypatch):
    """Patch httpx.AsyncClient so create/update never hit the network."""
    sent: dict = {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            sent["init_kwargs"] = kw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, *, headers, json):
            sent["method"] = "POST"
            sent["url"] = url
            sent["headers"] = headers
            sent["body"] = json
            return sent.get("response") or _mock_response(200, {"id": "evt-created-xyz"})

        async def patch(self, url, *, headers, json):
            sent["method"] = "PATCH"
            sent["url"] = url
            sent["headers"] = headers
            sent["body"] = json
            return sent.get("response") or _mock_response(200, {"id": "evt-updated-xyz"})

    monkeypatch.setattr("app.mcp.calendar_client.httpx.AsyncClient", _FakeClient)
    return sent


@pytest.mark.asyncio
async def test_create_event_posts_all_day_body_with_exclusive_end(fake_http_client):
    client = CalendarMCPClient(access_token="tok-abc")
    out = await client.create_event(
        title="Submit Q2 report",
        date_iso="2026-06-20",
        description="Task abc-123",
    )
    assert fake_http_client["method"] == "POST"
    assert fake_http_client["url"] == _CALENDAR_EVENTS_URL
    assert fake_http_client["headers"]["Authorization"] == "Bearer tok-abc"
    assert fake_http_client["headers"]["Content-Type"] == "application/json"
    # All-day body: start=date, end=date+1 (exclusive per Google's contract)
    assert fake_http_client["body"] == {
        "summary": "Submit Q2 report",
        "start": {"date": "2026-06-20"},
        "end": {"date": "2026-06-21"},
        "description": "Task abc-123",
    }
    # Response wrapping: Google returns ``id``, we surface ``event_id``.
    assert out["event_id"] == "evt-created-xyz"


@pytest.mark.asyncio
async def test_create_event_omits_description_when_none(fake_http_client):
    client = CalendarMCPClient(access_token="tok-abc")
    await client.create_event(title="x", date_iso="2026-06-20")
    assert "description" not in fake_http_client["body"]


@pytest.mark.asyncio
async def test_update_event_patches_event_id_url(fake_http_client):
    client = CalendarMCPClient(access_token="tok-abc")
    out = await client.update_event(
        event_id="existing-evt-id",
        title="Renamed",
        date_iso="2026-06-20",
    )
    assert fake_http_client["method"] == "PATCH"
    assert fake_http_client["url"] == f"{_CALENDAR_EVENTS_URL}/existing-evt-id"
    assert fake_http_client["body"]["summary"] == "Renamed"
    assert out["event_id"] == "evt-updated-xyz"


@pytest.mark.asyncio
async def test_update_event_falls_back_to_passed_event_id_when_response_omits_id(fake_http_client):
    fake_http_client["response"] = _mock_response(200, {})  # no "id" key
    client = CalendarMCPClient(access_token="tok-abc")
    out = await client.update_event(event_id="passed-id", title="x", date_iso="2026-06-20")
    assert out["event_id"] == "passed-id"


@pytest.mark.asyncio
async def test_403_raises_runtime_error_with_status_in_message(fake_http_client):
    fake_http_client["response"] = _mock_response(
        403, text="Calendar usage limits exceeded"
    )
    client = CalendarMCPClient(access_token="tok-abc")
    with pytest.raises(RuntimeError) as exc_info:
        await client.create_event(title="x", date_iso="2026-06-20")
    msg = str(exc_info.value)
    # notification_service.py does ``"403" in str(exc)`` and queue_consumer.py
    # does ``" 403" in joined or "[403]" in joined`` — both must match.
    assert "403" in msg
    assert "[403]" in msg
    assert "Calendar" in msg


@pytest.mark.asyncio
async def test_401_invalid_token_raises_with_status_so_auth_detector_fires(fake_http_client):
    fake_http_client["response"] = _mock_response(401, text="invalid_grant")
    client = CalendarMCPClient(access_token="tok-stale")
    with pytest.raises(RuntimeError, match=r"\[401\]"):
        await client.create_event(title="x", date_iso="2026-06-20")


@pytest.mark.asyncio
async def test_end_exclusive_rule_handles_month_boundary(fake_http_client):
    client = CalendarMCPClient(access_token="tok")
    await client.create_event(title="x", date_iso="2026-06-30")
    assert fake_http_client["body"]["start"] == {"date": "2026-06-30"}
    assert fake_http_client["body"]["end"] == {"date": "2026-07-01"}


@pytest.mark.asyncio
async def test_end_exclusive_rule_handles_year_boundary(fake_http_client):
    client = CalendarMCPClient(access_token="tok")
    await client.create_event(title="x", date_iso="2026-12-31")
    assert fake_http_client["body"]["start"] == {"date": "2026-12-31"}
    assert fake_http_client["body"]["end"] == {"date": "2027-01-01"}


# ---------------------------------------------------------------------------
# Round 13 (2026-05-31) — timed events when deadline_time is set
# ---------------------------------------------------------------------------
# When a task has a time-of-day (e.g. "3:00 PM"), the calendar event should
# render at that time in the user's local zone rather than as an all-day
# block. The all-day path (time_str=None) MUST stay byte-identical to the
# pre-Round-13 behaviour so existing date-only deadlines aren't visually
# disturbed in users' calendars.

@pytest.mark.asyncio
async def test_create_event_with_time_uses_datetime_body_and_default_ict_tz(fake_http_client):
    client = CalendarMCPClient(access_token="tok")
    out = await client.create_event(
        title="Submit Q2 report",
        date_iso="2026-06-20",
        description="Task abc",
        time_str="15:00:00",
    )
    body = fake_http_client["body"]
    # No all-day "date" key — the contract is dateTime + timeZone instead.
    assert "date" not in body["start"]
    assert "date" not in body["end"]
    assert body["start"]["dateTime"] == "2026-06-20T15:00:00"
    assert body["start"]["timeZone"] == "Asia/Ho_Chi_Minh"
    # Default 1-hour duration so the event is visible on the calendar grid.
    assert body["end"]["dateTime"] == "2026-06-20T16:00:00"
    assert body["end"]["timeZone"] == "Asia/Ho_Chi_Minh"
    assert body["description"] == "Task abc"
    assert out["event_id"] == "evt-created-xyz"


@pytest.mark.asyncio
async def test_create_event_without_time_keeps_all_day_body_unchanged(fake_http_client):
    """Regression guard: leaving time_str=None must produce the exact same
    all-day body the pre-Round-13 contract used."""
    client = CalendarMCPClient(access_token="tok")
    await client.create_event(title="x", date_iso="2026-06-20")
    body = fake_http_client["body"]
    assert body["start"] == {"date": "2026-06-20"}
    assert body["end"] == {"date": "2026-06-21"}
    assert "dateTime" not in body["start"]


@pytest.mark.asyncio
async def test_create_event_handles_evening_time_within_same_day(fake_http_client):
    """11 PM + 1h = midnight next day — make sure the date math is correct
    across day boundaries."""
    client = CalendarMCPClient(access_token="tok")
    await client.create_event(title="x", date_iso="2026-06-20", time_str="23:00:00")
    body = fake_http_client["body"]
    assert body["start"]["dateTime"] == "2026-06-20T23:00:00"
    assert body["end"]["dateTime"] == "2026-06-21T00:00:00"


@pytest.mark.asyncio
async def test_update_event_with_time_uses_datetime_body(fake_http_client):
    """Symmetry with create — the calendar-resync path uses update, and a
    task whose time was set after initial create must flip its existing
    all-day event into a timed event."""
    client = CalendarMCPClient(access_token="tok")
    out = await client.update_event(
        event_id="existing-evt",
        title="Renamed",
        date_iso="2026-06-20",
        time_str="09:30:00",
    )
    body = fake_http_client["body"]
    assert body["start"]["dateTime"] == "2026-06-20T09:30:00"
    assert body["end"]["dateTime"] == "2026-06-20T10:30:00"
    assert out["event_id"] == "evt-updated-xyz"


@pytest.mark.asyncio
async def test_create_event_accepts_hh_mm_without_seconds(fake_http_client):
    """notification_service emits time as ``HH:MM:SS`` but a UI-direct edit
    might emit ``HH:MM``. Both must parse — keeps the contract permissive."""
    client = CalendarMCPClient(access_token="tok")
    await client.create_event(title="x", date_iso="2026-06-20", time_str="14:30")
    body = fake_http_client["body"]
    assert body["start"]["dateTime"] == "2026-06-20T14:30:00"
