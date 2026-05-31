"""Shared scheduler runtime: Redis client + progress publishing + sync state.

Imported by every processor module so they can publish progress and update the
``sync_states`` row without each one re-deriving how Redis is reached.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.sync_state import SyncState

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=float(settings.redis_socket_connect_timeout_seconds),
        )
        try:
            await asyncio.wait_for(
                client.ping(),
                timeout=float(settings.redis_socket_connect_timeout_seconds),
            )
        except Exception as exc:
            logger.error(
                "Redis unreachable at %s (%s). Set REDIS_PUBLISH_PORT or REDIS_URL to the host-published "
                "port from Docker/OrbStack (e.g. mapping 56379:6379 → use 56379 on the host).",
                settings.redis_url,
                type(exc).__name__,
                exc_info=exc,
            )
            raise
        logger.info("Redis queue client connected (%s)", settings.redis_url)
        _redis = client
    return _redis


async def publish_progress(
    user_id: str,
    source: str,
    step: str,
    detail: str = "",
    current: int = 0,
    total: int = 0,
) -> None:
    r = await get_redis()
    key = f"sync:progress:{user_id}:{source}"
    payload = json.dumps(
        {
            "step": step,
            "detail": detail,
            "current": current,
            "total": total,
            "ts": datetime.now(UTC).isoformat(),
        }
    )
    await r.set(key, payload, ex=300)


async def clear_progress(user_id: str, source: str) -> None:
    r = await get_redis()
    await r.delete(f"sync:progress:{user_id}:{source}")


async def ensure_sync_state(
    user_id: uuid.UUID,
    source_type: str,
    status: str,
    error: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = select(SyncState).where(
                SyncState.user_id == user_id,
                SyncState.source_type == source_type,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                row = SyncState(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    source_type=source_type,
                )
                session.add(row)
            row.status = status
            if status in ("idle", "error"):
                row.last_sync_at = datetime.now(UTC)
            if error:
                row.error_message = error
            elif status != "error":
                row.error_message = None
