"""Daily Digest processor — build the user's end-of-day digest and self-send."""

from __future__ import annotations

from app.services.observability import record_pipeline_error

from .._runtime import logger


async def process_daily_digest_job(user_id: str, access_token: str) -> None:
    """Build and self-send the Daily Digest (Round 9, 2026-05-30).

    Sibling of ``process_weekly_brief_job`` — same fail-safe semantics:
    missing gmail.send scope yields a 403 which is recorded, not raised.
    """
    from app.services.daily_digest_service import async_send_daily_digest

    result = await async_send_daily_digest(user_id, access_token)
    if result.get("sent"):
        logger.info("daily_digest ok: user=%s", user_id)
        return
    errors = result.get("errors") or ["unknown failure"]
    record_pipeline_error(
        source_type="daily_digest",
        user_id=user_id,
        error="; ".join(errors)[:300],
    )
