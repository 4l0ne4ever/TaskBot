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

from datetime import date, datetime, time, timedelta
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
    def _timed_body(
        *,
        title: str,
        date_iso: str,
        time_str: str,
        description: str | None,
        tz: str = "Asia/Ho_Chi_Minh",
    ) -> dict[str, Any]:
        """Round 13 (2026-05-31): when the source said a time-of-day,
        create a *timed* event instead of all-day. Default duration is one
        hour (matches "rough reminder of when something is due" semantics —
        nobody puts a specific end time on "submit by 5 PM"). Timezone
        defaults to ICT because the dogfood account is Vietnam-based; this
        is a defensible per-deployment default that the panel can ask about.

        Body shape uses Google Calendar's ``start.dateTime`` + ``timeZone``
        contract — Google interprets the date-time string in the given
        timezone.
        """
        t = time.fromisoformat(time_str[:8] if len(time_str) >= 8 else time_str)
        start_dt = datetime.combine(date.fromisoformat(date_iso), t)
        end_dt = start_dt + timedelta(hours=1)
        body: dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat(timespec="seconds"), "timeZone": tz},
            "end":   {"dateTime": end_dt.isoformat(timespec="seconds"),   "timeZone": tz},
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

    @staticmethod
    def _maybe_attach_recurrence(body: dict[str, Any], recurrence_rule: str | None) -> dict[str, Any]:
        """Phase 6.6 (2026-06-03): inject ``recurrence`` array when an RRULE is
        provided. Google Calendar expects a list of RFC 5545 lines — for a
        single rule that is ``[f"RRULE:{rule}"]``. The rule must NOT include
        the ``RRULE:`` prefix in TaskBot's stored field; we prepend it here.
        """
        if recurrence_rule:
            body = dict(body)
            body["recurrence"] = [f"RRULE:{recurrence_rule}"]
        return body

    async def create_event(
        self,
        *,
        title: str,
        date_iso: str,
        description: str | None = None,
        time_str: str | None = None,
        recurrence_rule: str | None = None,
    ) -> dict[str, Any]:
        """POST a new event. Timed (``time_str`` set) or all-day (``time_str``
        None — pre-Round-13 behaviour exactly preserved). When
        ``recurrence_rule`` is provided (Phase 6.6), the event is created as
        a recurring series with that RRULE. Returns
        ``{"event_id": <google-event-id>}``."""
        body = (
            self._timed_body(title=title, date_iso=date_iso, time_str=time_str, description=description)
            if time_str
            else self._all_day_body(title=title, date_iso=date_iso, description=description)
        )
        body = self._maybe_attach_recurrence(body, recurrence_rule)
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
        time_str: str | None = None,
        recurrence_rule: str | None = None,
    ) -> dict[str, Any]:
        """PATCH an existing event (idempotent). Timed or all-day per
        ``time_str``. When ``recurrence_rule`` changes between calls, Google
        propagates the new RRULE to all future occurrences (existing past
        occurrences keep their original RRULE). Pass ``recurrence_rule=None``
        with a recurring event to clear the recurrence — the PATCH body
        omits the ``recurrence`` key and Google retains the prior value, so
        use ``delete_event`` + ``create_event`` for the remove-recurrence
        flow (the frontend Remove-recurrence path follows this contract).
        Returns ``{"event_id": ...}``."""
        body = (
            self._timed_body(title=title, date_iso=date_iso, time_str=time_str, description=description)
            if time_str
            else self._all_day_body(title=title, date_iso=date_iso, description=description)
        )
        body = self._maybe_attach_recurrence(body, recurrence_rule)
        url = f"{_CALENDAR_EVENTS_URL}/{event_id}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.patch(url, headers=self._headers(), json=body)
        self._raise_for_status(resp, "update_event")
        data = resp.json()
        # Google preserves ``id`` on PATCH; fall back to the passed event_id
        # just in case the response shape varies.
        return {"event_id": data.get("id") or event_id, "raw": data}

    async def delete_event(self, *, event_id: str) -> None:
        """DELETE an event by id. Used by the Remove-recurrence flow
        (Phase 6.6) before recreating as a single event at the next
        occurrence date. Idempotent — Google returns 410 GONE when the event
        was already deleted, which we treat as success."""
        url = f"{_CALENDAR_EVENTS_URL}/{event_id}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.delete(url, headers=self._headers())
        if resp.status_code in (200, 204, 410):
            return
        self._raise_for_status(resp, "delete_event")
