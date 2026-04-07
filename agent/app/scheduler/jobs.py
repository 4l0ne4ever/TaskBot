import json
import logging
from urllib.parse import urlparse

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)
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


def _decrypt_token(encrypted: str) -> dict | None:
    try:
        fernet = Fernet(settings.encryption_key.strip().encode())
        return json.loads(fernet.decrypt(encrypted.encode()))
    except (InvalidToken, Exception):
        return None


async def _get_sync_eligible_users() -> list[dict]:
    """Query all users with a valid oauth_token and return their id + access_token."""
    users: list[dict] = []
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.oauth_token.isnot(None))
        result = await session.execute(stmt)
        for user in result.scalars().all():
            tokens = _decrypt_token(user.oauth_token)
            if tokens and tokens.get("access_token"):
                users.append({
                    "id": str(user.id),
                    "access_token": tokens["access_token"],
                })
    return users


async def sync_all_users_gmail() -> None:
    import redis.asyncio as aioredis

    users = await _get_sync_eligible_users()
    if not users:
        logger.debug("auto-sync gmail: no eligible users")
        return
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        for u in users:
            job = json.dumps({
                "user_id": u["id"],
                "source_type": "gmail",
                "access_token": u["access_token"],
                "triggered_by": "auto",
                "time_range": "1d",
            })
            await r.rpush(settings.pipeline_queue_name, job)
        logger.info("auto-sync gmail: enqueued %d users", len(users))
    finally:
        await r.aclose()


async def sync_all_users_drive() -> None:
    import redis.asyncio as aioredis

    users = await _get_sync_eligible_users()
    if not users:
        logger.debug("auto-sync drive: no eligible users")
        return
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        for u in users:
            job = json.dumps({
                "user_id": u["id"],
                "source_type": "drive",
                "access_token": u["access_token"],
                "triggered_by": "auto",
                "time_range": "1d",
            })
            await r.rpush(settings.pipeline_queue_name, job)
        logger.info("auto-sync drive: enqueued %d users", len(users))
    finally:
        await r.aclose()


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
    logger.info(
        "scheduler started — gmail every %dm, drive every %dm",
        settings.sync_gmail_interval_minutes,
        settings.sync_drive_interval_minutes,
    )
