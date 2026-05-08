from datetime import UTC, datetime

import redis.asyncio as redis  # pyright: ignore[reportMissingImports]

from app.config import get_settings
from app.mcp.drive_client import DriveMCPClient
from app.mcp.gmail_client import GmailMCPClient

settings = get_settings()


def _dedupe_files_by_id(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        fid = str(item.get("id") or "")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        out.append(item)
    return out


def _gmail_limit_for_profile(sync_profile: str) -> int:
    if sync_profile == "strict_work":
        return settings.strict_work_max_gmail_messages_per_sync
    if sync_profile == "broad":
        return settings.broad_max_gmail_messages_per_sync
    return settings.balanced_max_gmail_messages_per_sync


def _drive_limit_for_profile(sync_profile: str) -> int:
    if sync_profile == "strict_work":
        return settings.strict_work_max_drive_files_per_sync
    if sync_profile == "broad":
        return settings.broad_max_drive_files_per_sync
    return settings.balanced_max_drive_files_per_sync


async def _get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _gmail_cursor_key(user_id: str) -> str:
    return f"sync:cursor:gmail:{user_id}"


def _drive_cursor_key(user_id: str) -> str:
    return f"sync:cursor:drive:{user_id}"


def _sync_lock_key(user_id: str, source: str) -> str:
    return f"sync:lock:{source}:{user_id}"


async def acquire_sync_lock(user_id: str, source: str, ttl_seconds: int = 300) -> bool:
    client = await _get_redis_client()
    result = await client.set(_sync_lock_key(user_id, source), "1", ex=ttl_seconds, nx=True)
    return bool(result)


async def release_sync_lock(user_id: str, source: str) -> None:
    client = await _get_redis_client()
    await client.delete(_sync_lock_key(user_id, source))


async def get_gmail_last_history_id(user_id: str) -> str | None:
    client = await _get_redis_client()
    value = await client.get(_gmail_cursor_key(user_id))
    return value if value else None


async def set_gmail_last_history_id(user_id: str, history_id: str) -> None:
    client = await _get_redis_client()
    await client.set(_gmail_cursor_key(user_id), history_id)


async def get_drive_last_page_token(user_id: str) -> str | None:
    client = await _get_redis_client()
    value = await client.get(_drive_cursor_key(user_id))
    return value if value else None


async def set_drive_last_page_token(user_id: str, page_token: str) -> None:
    client = await _get_redis_client()
    await client.set(_drive_cursor_key(user_id), page_token)


async def pull_recent_gmail_messages(
    *,
    user_id: str,
    access_token: str,
    last_sync_at: datetime | None = None,
    sync_profile: str = "balanced",
) -> list[dict]:
    gmail = GmailMCPClient(access_token=access_token)
    max_results = _gmail_limit_for_profile(sync_profile)
    messages = await gmail.list_messages(
        last_sync_at=last_sync_at,
        max_results=max_results,
        sync_profile=sync_profile,
    )
    if messages:
        latest_history_id = str(messages[0].get("history_id") or messages[0].get("historyId") or "")
        if latest_history_id:
            await set_gmail_last_history_id(user_id, latest_history_id)
    return messages


def now_utc() -> datetime:
    return datetime.now(UTC)


async def pull_recent_drive_files(
    *,
    user_id: str,
    access_token: str,
    last_sync_at: datetime | None = None,
    sync_profile: str = "balanced",
) -> list[dict]:
    drive = DriveMCPClient(access_token=access_token)
    limit = _drive_limit_for_profile(sync_profile)
    owned = await drive.list_files(
        last_sync_at=last_sync_at,
        page_size=limit,
        sync_profile=sync_profile,
    )
    shared: dict | list | None = {"files": []}
    if sync_profile != "strict_work":
        shared = await drive.list_shared_files(
            last_sync_at=last_sync_at,
            page_size=limit,
            sync_profile=sync_profile,
        )

    owned_files = owned.get("files") if isinstance(owned, dict) else []
    shared_files = shared.get("files") if isinstance(shared, dict) else []
    all_files: list[dict] = []
    if isinstance(owned_files, list):
        all_files.extend(owned_files)
    if isinstance(shared_files, list):
        all_files.extend(shared_files)

    all_files = _dedupe_files_by_id(all_files)
    if len(all_files) > limit:
        all_files = all_files[:limit]

    page_token = owned.get("next_page_token") or owned.get("nextPageToken")
    if isinstance(page_token, str) and page_token:
        await set_drive_last_page_token(user_id, page_token)

    return all_files


async def run_gmail_sync_for_user(
    *,
    user_id: str,
    access_token: str,
    last_sync_at: datetime | None = None,
    sync_profile: str = "balanced",
) -> list[dict]:
    lock_acquired = await acquire_sync_lock(user_id, "gmail")
    if not lock_acquired:
        return []
    try:
        return await pull_recent_gmail_messages(
            user_id=user_id,
            access_token=access_token,
            last_sync_at=last_sync_at,
            sync_profile=sync_profile,
        )
    finally:
        await release_sync_lock(user_id, "gmail")


async def run_drive_sync_for_user(
    *,
    user_id: str,
    access_token: str,
    last_sync_at: datetime | None = None,
    sync_profile: str = "balanced",
) -> list[dict]:
    lock_acquired = await acquire_sync_lock(user_id, "drive")
    if not lock_acquired:
        return []
    try:
        return await pull_recent_drive_files(
            user_id=user_id,
            access_token=access_token,
            last_sync_at=last_sync_at,
            sync_profile=sync_profile,
        )
    finally:
        await release_sync_lock(user_id, "drive")
