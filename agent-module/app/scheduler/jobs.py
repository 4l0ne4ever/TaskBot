from urllib.parse import urlparse

import httpx
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.services.sync_service import run_drive_sync_for_user, run_gmail_sync_for_user

settings = get_settings()
parsed_redis = urlparse(settings.redis_url)
redis_host = parsed_redis.hostname or "localhost"
redis_port = parsed_redis.port or 6379
redis_db = int(parsed_redis.path.lstrip("/") or "0")
redis_password = parsed_redis.password

scheduler = AsyncIOScheduler(
    jobstores={
        "default": RedisJobStore(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
        )
    },
    job_defaults={"coalesce": True, "max_instances": 1},
)


async def sync_all_users_gmail() -> None:
    users = await fetch_sync_enabled_users()
    for user in users:
        user_id = user.get("id")
        access_token = user.get("access_token")
        if user_id and access_token:
            await run_gmail_sync_for_user(user_id=user_id, access_token=access_token)


async def sync_all_users_drive() -> None:
    users = await fetch_sync_enabled_users()
    for user in users:
        user_id = user.get("id")
        access_token = user.get("access_token")
        if user_id and access_token:
            await run_drive_sync_for_user(user_id=user_id, access_token=access_token)


async def fetch_sync_enabled_users() -> list[dict]:
    # Placeholder source: backend API can expose a dedicated endpoint later.
    # For now, return empty list safely to avoid unintended polling side effects.
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.backend_api_base_url}/sync/status")
        if response.status_code >= 400:
            return []
    except Exception:
        return []
    return []


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.add_job(
        sync_all_users_gmail,
        "interval",
        minutes=settings.sync_gmail_interval_minutes,
        id="gmail_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_all_users_drive,
        "interval",
        minutes=settings.sync_drive_interval_minutes,
        id="drive_sync",
        replace_existing=True,
    )
    scheduler.start()
