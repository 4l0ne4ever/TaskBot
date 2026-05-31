"""Manager Weekly Brief processor — build the brief and self-send it."""

from __future__ import annotations

from app.services.observability import record_pipeline_error

from .._runtime import logger


async def process_weekly_brief_job(user_id: str, access_token: str) -> None:
    """Build and self-send the manager's Weekly Brief (Phase 8.3).

    Fail-safe like calendar dispatch: a missing gmail.send scope yields a 403
    which ``async_send_weekly_brief`` returns as an error rather than raising.
    Recorded (user-actionable: reconnect for send permission) and moved on.
    """
    from app.services.weekly_brief_service import async_send_weekly_brief

    result = await async_send_weekly_brief(user_id, access_token)
    if result.get("sent"):
        logger.info("weekly_brief ok: user=%s", user_id)
        return
    errors = result.get("errors") or ["unknown failure"]
    record_pipeline_error(
        source_type="weekly_brief",
        user_id=user_id,
        error="; ".join(errors)[:300],
    )
