"""LLM-pressure tracking: when the recent obs:llm:calls window shows too many
429s we throttle (skip remaining docs in a job) and, if the window is
saturated with daily-quota errors, defer rather than churn.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from ._runtime import get_redis, logger, settings

_DAILY_QUOTA_MARKERS = ("tokens per day", "(tpd)", "requests per day", "(rpd)")


def is_daily_quota_error_text(error_text: str) -> bool:
    t = (error_text or "").lower()
    return any(marker in t for marker in _DAILY_QUOTA_MARKERS)


async def llm_pressure_snapshot() -> tuple[bool, float, int, bool]:
    """Return ``(high_pressure, ratio, sample_size, daily_quota_exhausted)``.

    ``daily_quota_exhausted`` is True when the recent ``obs:llm:calls`` window
    is saturated with TPD/RPD 429s. Those reset at 00:00 UTC, so a minute-scale
    requeue is pointless — callers should defer to the day boundary (or fail
    the sync cleanly) instead of churning in a retry loop that burns Redis
    cycles and never recovers.

    Entries older than the current UTC day are excluded: TPD/RPD quotas reset
    at UTC midnight, so yesterday's errors must not block today's syncs even
    when those entries happen to be at the head of the Redis list.
    """
    r = await get_redis()
    window = max(settings.llm_pressure_window_size, 1)
    # Read a larger buffer so date-filtering doesn't silently under-sample
    # when today has fewer than ``window`` entries yet.
    rows = await r.lrange("obs:llm:calls", 0, window * 4 - 1)
    if not rows:
        return False, 0.0, 0, False

    utc_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    rate_limit_errors = 0
    daily_errors = 0
    valid = 0
    for row in rows:
        if valid >= window:
            break
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        ts_raw = payload.get("ts") or ""
        if ts_raw:
            try:
                entry_ts = datetime.fromisoformat(str(ts_raw))
                if entry_ts.tzinfo is None:
                    entry_ts = entry_ts.replace(tzinfo=UTC)
                if entry_ts < utc_today:
                    continue
            except (ValueError, TypeError):
                pass  # unparseable ts → include conservatively
        valid += 1
        error = str(payload.get("error") or "").lower()
        if "429" in error or "rate limit" in error or "rate_limit" in error:
            rate_limit_errors += 1
            kind = (payload.get("rate_limit_kind") or "").lower()
            if kind in {"tpd", "rpd"} or is_daily_quota_error_text(error):
                daily_errors += 1
    if valid == 0:
        return False, 0.0, 0, False
    ratio = rate_limit_errors / valid
    high = ratio >= settings.llm_rate_limit_error_threshold
    # Require a meaningful sample AND a majority-daily share so a single stale
    # TPD record can't freeze ingestion. Threshold mirrors the fallback routing
    # rule — if >=50% of recent rate-limited calls are daily-window, in-process
    # retry is a waste.
    daily_exhausted = (
        high
        and valid >= max(5, window // 4)
        and rate_limit_errors > 0
        and daily_errors / rate_limit_errors >= 0.5
    )
    return high, ratio, valid, daily_exhausted


async def requeue_deferred_job(job: dict, deferred: int) -> None:
    retry_count = int(job.get("retry_count", 0))
    if retry_count >= settings.llm_pressure_requeue_max_retries:
        logger.warning(
            "skip deferred requeue: reached retry cap (%s), source=%s, user=%s, deferred=%s",
            retry_count,
            job.get("source_type"),
            job.get("user_id"),
            deferred,
        )
        return

    requeue_job = dict(job)
    requeue_job["retry_count"] = retry_count + 1
    requeue_job["triggered_by"] = "throttled_retry"
    requeue_job["deferred_count_hint"] = deferred
    delay = max(settings.llm_pressure_requeue_delay_seconds, 0.0)
    if delay > 0:
        await asyncio.sleep(delay)
    r = await get_redis()
    await r.lpush(settings.pipeline_queue_name, json.dumps(requeue_job))
    logger.info(
        "requeued deferred job: source=%s user=%s deferred=%s retry=%s delay=%.1fs",
        requeue_job.get("source_type"),
        requeue_job.get("user_id"),
        deferred,
        requeue_job["retry_count"],
        delay,
    )
