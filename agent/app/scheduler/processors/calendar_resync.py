"""Calendar resync processor: after a conflict merge, update the surviving
task's Google Calendar event so the visible deadline matches the merged row.
"""

from __future__ import annotations

import asyncio

from app.services.observability import record_pipeline_error

from .._runtime import logger
from ..auth import is_auth_revoked_error

_CALENDAR_RESYNC_MAX_ATTEMPTS = 3
_CALENDAR_RESYNC_RETRY_DELAY_SECONDS = 2.0


async def process_calendar_resync_job(user_id: str, access_token: str, task_id: str) -> None:
    """Update the Google Calendar event for a single task after a conflict merge.

    Reuses ``async_dispatch_notifications`` (idempotent — calls ``update_event``
    when the task already has a ``calendar_event_id``). The backend only
    enqueues this job when the surviving task HAS a calendar event and a
    calendar-reflected field changed, so dispatch always lands on the update
    path, never create.

    In-handler bounded retry covers transient MCP/network blips. Auth-class
    failures (401/invalid_grant) are user-actionable — surfaced via
    ``record_pipeline_error`` and never retried (a revoked token won't recover
    on its own).
    """
    from app.services.notification_service import async_dispatch_notifications

    for attempt in range(1, _CALENDAR_RESYNC_MAX_ATTEMPTS + 1):
        state = {
            "user_id": user_id,
            "access_token": access_token,
            "saved_task_ids": [task_id],
        }
        result = await async_dispatch_notifications(state)
        task_errors = [e for e in result.get("errors", []) if task_id in e]
        if not task_errors:
            logger.info("calendar_resync ok: task=%s (attempt %s)", task_id, attempt)
            return
        joined = " ".join(task_errors)
        if is_auth_revoked_error(joined) or " 403" in joined or "[403]" in joined:
            record_pipeline_error(
                source_type="calendar_resync",
                user_id=user_id,
                error=f"task={task_id}: permanent calendar failure, not retrying: {joined[:300]}",
            )
            return
        if attempt < _CALENDAR_RESYNC_MAX_ATTEMPTS:
            logger.warning(
                "calendar_resync transient failure task=%s attempt=%s; retrying: %s",
                task_id, attempt, joined[:200],
            )
            await asyncio.sleep(_CALENDAR_RESYNC_RETRY_DELAY_SECONDS)
    record_pipeline_error(
        source_type="calendar_resync",
        user_id=user_id,
        error=f"task={task_id}: exhausted {_CALENDAR_RESYNC_MAX_ATTEMPTS} attempts",
    )
