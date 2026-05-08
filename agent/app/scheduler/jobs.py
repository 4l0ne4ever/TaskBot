import asyncio
import json
import logging
from urllib.parse import urlparse

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cryptography.fernet import Fernet, InvalidToken
import httpx
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


def _encrypt_token(token_dict: dict) -> str:
    fernet = Fernet(settings.encryption_key.strip().encode())
    return fernet.encrypt(json.dumps(token_dict).encode()).decode()


async def _refresh_access_token(refresh_token: str) -> tuple[dict | None, str | None]:
    """Refresh Google OAuth access token.

    Returns (tokens, error). On success: (data, None). On failure: (None, short_reason).
    The reason is a short classifier ("http_<code>", "transport", "invalid_response")
    so callers can surface actionable sync errors instead of silently retrying with
    a stale access token (observed cluster: MCP 401s after expired refresh tokens).
    """
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data=payload)
    except Exception as exc:
        return None, f"transport:{type(exc).__name__}"
    if resp.status_code >= 400:
        body = ""
        try:
            body = resp.text[:160]
        except Exception:
            body = ""
        return None, f"http_{resp.status_code}:{body}".strip()
    try:
        data = resp.json()
    except Exception:
        return None, "invalid_response:json"
    if not isinstance(data, dict) or not data.get("access_token"):
        return None, "invalid_response:no_access_token"
    return data, None


async def _get_sync_eligible_users() -> list[dict]:
    """Query all users with a valid oauth_token and return their id + access_token.

    If a user has a refresh_token but refreshing it fails (e.g., user revoked at
    Google, refresh_token expired after 6 months of inactivity, or the OAuth
    client rotated), we SKIP the user instead of reusing a stale access_token.
    Reusing the stale token previously produced downstream MCP 401s on every
    sync tick — visible in obs:pipeline:errors but not actionable for the user.
    """
    from app.services.observability import record_pipeline_error

    users: list[dict] = []
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = select(User).where(User.oauth_token.isnot(None))
            result = await session.execute(stmt)
            for user in result.scalars().all():
                tokens = _decrypt_token(user.oauth_token)
                if not tokens:
                    continue

                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")

                if refresh_token:
                    refreshed, refresh_error = await _refresh_access_token(str(refresh_token))
                    if refreshed and refreshed.get("access_token"):
                        access_token = refreshed["access_token"]
                        updated_tokens = dict(tokens)
                        updated_tokens["access_token"] = access_token
                        if refreshed.get("expires_in") is not None:
                            updated_tokens["expires_in"] = refreshed["expires_in"]
                        if refreshed.get("scope") is not None:
                            updated_tokens["scope"] = refreshed["scope"]
                        if refreshed.get("token_type") is not None:
                            updated_tokens["token_type"] = refreshed["token_type"]
                        user.oauth_token = _encrypt_token(updated_tokens)
                    else:
                        reason = refresh_error or "unknown"
                        logger.warning(
                            "oauth refresh failed for user %s — skipping sync (reason=%s)",
                            user.id,
                            reason,
                        )
                        try:
                            record_pipeline_error(
                                source_type="oauth_refresh",
                                user_id=str(user.id),
                                error=f"refresh_failed: {reason}",
                            )
                        except Exception:
                            pass
                        continue

                if access_token:
                    users.append({
                        "id": str(user.id),
                        "access_token": str(access_token),
                        "sync_profile": (user.sync_config or {}).get("sync_profile", "balanced"),
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
                "sync_profile": u.get("sync_profile", "balanced"),
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
                "sync_profile": u.get("sync_profile", "balanced"),
            })
            await r.rpush(settings.pipeline_queue_name, job)
        logger.info("auto-sync drive: enqueued %d users", len(users))
    finally:
        await r.aclose()


async def _gemini_keepalive_job() -> None:
    from app.pipeline.llm import warmup_gemini_connection

    try:
        await asyncio.to_thread(warmup_gemini_connection)
    except Exception:
        logger.exception("gemini keepalive job failed")


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
    ka = settings.gemini_keepalive_interval_minutes
    if (
        ka is not None
        and int(ka) > 0
        and settings.gemini_api_key
        and str(settings.gemini_api_key).strip()
    ):
        scheduler.add_job(
            _gemini_keepalive_job,
            "interval",
            minutes=max(1, int(ka)),
            id="gemini_keepalive",
            replace_existing=True,
        )
        logger.info("scheduler: gemini keepalive every %dm", max(1, int(ka)))
    scheduler.start()
    logger.info(
        "scheduler started — gmail every %dm, drive every %dm",
        settings.sync_gmail_interval_minutes,
        settings.sync_drive_interval_minutes,
    )
