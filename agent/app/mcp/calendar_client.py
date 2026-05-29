"""Direct Google Calendar REST v3 client.

Historically this was an MCP shim (``CalendarMCPClient`` extending
``BaseMCPClient``) that proxied through Anthropic's hosted gcal MCP server.
That endpoint went 404 in production (verified 2026-05-30 via direct invocation
against a real OAuth token), so this module now calls the Google Calendar API
directly via ``httpx`` using the user's OAuth bearer token.

The class name ``CalendarMCPClient`` is preserved for backward compatibility —
``notification_service.dispatch_notifications_sync`` and four unit tests in
``test_notification_confirm_gate.py`` import and mock the class by that name.
Renaming would force test churn for zero behavioural gain.

All events are created as **all-day** events because ``tasks.deadline`` is
stored as ``DATE`` (no time component). Google Calendar's all-day event
contract requires an *exclusive* end date — i.e. an event "on" 2026-06-20
sends ``start={"date":"2026-06-20"}`` and ``end={"date":"2026-06-21"}``.
Time-of-day extraction (e.g. "5 PM ICT") and timezone normalisation are
documented future work in ``tests/e2e/real-world-validation.md`` §6.

Error semantics preserve what callers already depend on:

- ``notification_service`` checks ``"403" in str(exc)`` to flip
  ``calendar_blocked = True`` (skip remaining tasks in the batch).
- ``queue_consumer._process_calendar_resync_job`` checks for ``" 403"`` or
  ``"[403]"`` and treats those as permanent (no retry).

Both checks see the status code via the formatted ``RuntimeError`` message
``"Google Calendar {op} failed [{status}]: {body[:300]}"``.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_DEFAULT_TIMEOUT_SECONDS = 30.0


class CalendarMCPClient:
    """Historical name (was an MCP shim). Calls Google Calendar REST v3 directly."""

    def __init__(self, access_token: str, *, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS):
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds

    # ── internals ────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _all_day_body(*, title: str, date_iso: str, description: str | None) -> dict[str, Any]:
        start = date.fromisoformat(date_iso)
        end_exclusive = (start + timedelta(days=1)).isoformat()
        body: dict[str, Any] = {
            "summary": title,
            "start": {"date": date_iso},
            "end": {"date": end_exclusive},
        }
        if description:
            body["description"] = description
        return body

    @staticmethod
    def _raise_for_status(resp: httpx.Response, op: str) -> None:
        if resp.is_success:
            return
        # Status code is embedded in the message string so the existing 403
        # / auth-revoked detectors in notification_service and queue_consumer
        # keep working unchanged. Truncate the body to keep errors readable.
        body_excerpt = (resp.text or "")[:300]
        raise RuntimeError(
            f"Google Calendar {op} failed [{resp.status_code}]: {body_excerpt}"
        )

    # ── public API (signatures preserved from the MCP-era client) ───────────

    async def create_event(
        self,
        *,
        title: str,
        date_iso: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """POST a new all-day event. Returns ``{"event_id": <google-event-id>}``."""
        body = self._all_day_body(title=title, date_iso=date_iso, description=description)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(_CALENDAR_EVENTS_URL, headers=self._headers(), json=body)
        self._raise_for_status(resp, "create_event")
        data = resp.json()
        # Google returns ``id``; notification_service consumes ``event_id``.
        return {"event_id": data.get("id"), "raw": data}

    async def update_event(
        self,
        *,
        event_id: str,
        title: str,
        date_iso: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """PATCH an existing event (idempotent). Returns ``{"event_id": ...}``."""
        body = self._all_day_body(title=title, date_iso=date_iso, description=description)
        url = f"{_CALENDAR_EVENTS_URL}/{event_id}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.patch(url, headers=self._headers(), json=body)
        self._raise_for_status(resp, "update_event")
        data = resp.json()
        # Google preserves ``id`` on PATCH; fall back to the passed event_id
        # just in case the response shape varies.
        return {"event_id": data.get("id") or event_id, "raw": data}
