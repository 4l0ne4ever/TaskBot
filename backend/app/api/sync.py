import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.pipeline_run import PipelineRun
from app.models.sync_state import SyncState
from app.models.user import User
from app.schemas.sync import PipelineRunResponse, SyncStateResponse
from app.services.auth_service import (
    decrypt_token,
    encrypt_token,
    merge_refreshed_tokens,
    refresh_google_access_token,
)

router = APIRouter()


@router.get("/status", response_model=list[SyncStateResponse])
async def sync_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SyncState]:
    stmt = (
        select(SyncState)
        .where(SyncState.user_id == current_user.id)
        .order_by(SyncState.source_type)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/trigger")
async def sync_trigger(
    source: str = Query(..., pattern=r"^(gmail|drive)$"),
    time_range: str = Query("1d", pattern=r"^(12h|1d|3d|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if not current_user.oauth_token:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_GOOGLE_TOKEN", "message": "Google account not connected"},
        )

    stmt = select(SyncState).where(
        SyncState.user_id == current_user.id, SyncState.source_type == source
    )
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    if state and state.status == "running":
        raise HTTPException(
            status_code=409,
            detail={"code": "SYNC_IN_PROGRESS", "message": f"{source} sync already running"},
        )

    settings = get_settings()
    try:
        tokens = decrypt_token(current_user.oauth_token)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Stored Google token is invalid"},
        ) from exc
    if not isinstance(tokens, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Stored Google token is invalid"},
        )
    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if refresh_token:
        refreshed, refresh_error = await refresh_google_access_token(refresh_token)
        if refreshed and refreshed.get("access_token"):
            merged_tokens = merge_refreshed_tokens(tokens, refreshed)
            access_token = str(merged_tokens.get("access_token") or "").strip()
            current_user.oauth_token = encrypt_token(merged_tokens)
        else:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "GOOGLE_AUTH_EXPIRED",
                    "message": "Google authorization expired. Reconnect Google account in Settings.",
                    "reason": refresh_error or "refresh_failed",
                },
            )
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail={"code": "GOOGLE_AUTH_EXPIRED", "message": "Missing Google access token"},
        )

    redis_client = await get_redis()
    job_payload = {
        "user_id": str(current_user.id),
        "source_type": source,
        "access_token": access_token,
        "triggered_by": "manual",
        "time_range": time_range,
        "sync_profile": (current_user.sync_config or {}).get("sync_profile", "balanced"),
    }
    await redis_client.rpush(settings.pipeline_queue_name, json.dumps(job_payload))
    return {"status": "queued", "source": source}


@router.get("/progress")
async def sync_progress(
    source: str = Query(..., pattern=r"^(gmail|drive)$"),
    current_user: User = Depends(get_current_user),
) -> dict:
    redis_client = await get_redis()
    key = f"sync:progress:{current_user.id}:{source}"
    raw = await redis_client.get(key)
    if not raw:
        return {"active": False, "step": "", "detail": "", "current": 0, "total": 0}
    data = json.loads(raw)
    return {"active": True, **data}


@router.post("/clear")
async def sync_clear(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Reset all sync states to idle and clear progress keys from Redis."""
    stmt = (
        update(SyncState)
        .where(SyncState.user_id == current_user.id)
        .values(status="idle", error_message=None)
    )
    await db.execute(stmt)
    await db.commit()

    redis_client = await get_redis()
    for source in ("gmail", "drive"):
        await redis_client.delete(
            f"sync:progress:{current_user.id}:{source}",
            f"sync:disabled:{current_user.id}:{source}",
            f"mcp:auth_streak:{current_user.id}:{source}",
        )
    return {"status": "cleared"}


@router.get("/history", response_model=list[PipelineRunResponse])
async def sync_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PipelineRun]:
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.user_id == current_user.id)
        .order_by(PipelineRun.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
