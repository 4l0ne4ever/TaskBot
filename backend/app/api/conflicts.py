import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select, update as _update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.conflict import Conflict
from app.models.task import Task
from app.models.user import User
from app.schemas.conflict import (
    CalendarSyncInfo,
    ConflictMerge,
    ConflictMergeResponse,
    ConflictResolve,
    ConflictResponse,
)
from app.services.auth_service import (
    decrypt_token,
    encrypt_token,
    merge_refreshed_tokens,
    refresh_google_access_token,
)

router = APIRouter()


async def _build_calendar_resync_payload(user: User) -> tuple[str | None, CalendarSyncInfo]:
    """Decrypt + refresh the user's Google token for a calendar resync job.

    Mirrors the token dance in ``sync.sync_trigger`` (the agent never decrypts
    — it consumes a plaintext ``access_token`` from the Redis payload). Returns
    ``(access_token, info)``; ``access_token`` is None when the token is
    missing/expired, in which case ``info`` explains why so the merge still
    succeeds and the UI can prompt a reconnect.
    """
    if not user.oauth_token:
        return None, CalendarSyncInfo(
            status="skipped",
            reason="no_token",
            message="Reconnect Google to sync the calendar event.",
        )
    try:
        tokens = decrypt_token(user.oauth_token)
    except Exception:
        return None, CalendarSyncInfo(
            status="skipped",
            reason="token_expired",
            message="Reconnect Google to sync the calendar event.",
        )
    if not isinstance(tokens, dict):
        return None, CalendarSyncInfo(
            status="skipped", reason="token_expired",
            message="Reconnect Google to sync the calendar event.",
        )
    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if refresh_token:
        refreshed, _err = await refresh_google_access_token(refresh_token)
        if refreshed and refreshed.get("access_token"):
            merged = merge_refreshed_tokens(tokens, refreshed)
            access_token = str(merged.get("access_token") or "").strip()
            user.oauth_token = encrypt_token(merged)
        else:
            return None, CalendarSyncInfo(
                status="skipped", reason="token_expired",
                message="Reconnect Google to sync the calendar event.",
            )
    if not access_token:
        return None, CalendarSyncInfo(
            status="skipped", reason="token_expired",
            message="Reconnect Google to sync the calendar event.",
        )
    return access_token, CalendarSyncInfo(
        status="queued", reason=None, message="Calendar syncing in background.",
    )


# Canonical scope ordering by cost-of-ignoring (Phase 2.3 UX hierarchy).
# multi_source has the highest cost (information siloed across platforms);
# intra_batch the lowest (often just an LLM artifact within a single source).
# NULL — legacy rows that pre-date Phase A' — falls to the bottom of the list.
# The order is enforced at the API layer rather than in the DB so a new scope
# value doesn't require a schema migration to slot in.
SCOPE_PRIORITY: tuple[str, ...] = (
    "multi_source",
    "thread_update",
    "inter_doc",
    "intra_batch",
)
_SCOPE_PRIORITY_MAP = {s: i + 1 for i, s in enumerate(SCOPE_PRIORITY)}


@router.get("", response_model=list[ConflictResponse])
async def list_conflicts(
    resolved: bool | None = Query(None),
    scope: str | None = Query(
        None,
        description=(
            "Filter by conflict scope. Accepts any of: multi_source, "
            "thread_update, inter_doc, intra_batch. Omit to return all."
        ),
    ),
    sort: str = Query(
        "created_at",
        pattern=r"^(created_at|priority)$",
        description=(
            "Ordering. 'created_at' (default) returns newest first. "
            "'priority' returns conflicts grouped by the cost-of-ignoring "
            "hierarchy (multi_source > thread_update > inter_doc > "
            "intra_batch), then by created_at within each group."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Conflict]:
    stmt = select(Conflict).where(Conflict.user_id == current_user.id)
    if resolved is not None:
        stmt = stmt.where(Conflict.resolved == resolved)
    if scope is not None:
        stmt = stmt.where(Conflict.scope == scope)
    if sort == "priority":
        # SQL CASE keeps the hierarchy stable even if the column is NULL
        # (legacy rows sort last) and avoids fetching every row into Python
        # just to re-sort it — important for the conflict-resolution page
        # that may render hundreds of rows.
        priority = case(
            _SCOPE_PRIORITY_MAP,
            value=Conflict.scope,
            else_=len(SCOPE_PRIORITY) + 1,
        )
        stmt = stmt.order_by(priority, Conflict.created_at.desc())
    else:
        stmt = stmt.order_by(Conflict.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/dismiss-all")
async def dismiss_all_conflicts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    stmt = (
        _update(Conflict)
        .where(Conflict.user_id == current_user.id, Conflict.resolved == False)  # noqa: E712
        .values(resolved=True, description="[resolved:dismiss_all]")
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"dismissed": result.rowcount}


@router.patch("/{conflict_id}", response_model=ConflictResponse)
async def resolve_conflict(
    conflict_id: UUID,
    body: ConflictResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conflict:
    stmt = select(Conflict).where(Conflict.id == conflict_id, Conflict.user_id == current_user.id)
    result = await db.execute(stmt)
    conflict = result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(
            status_code=404, detail={"code": "CONFLICT_NOT_FOUND", "message": "Conflict not found"}
        )
    if conflict.resolved:
        raise HTTPException(
            status_code=409, detail={"code": "ALREADY_RESOLVED", "message": "Conflict already resolved"}
        )

    conflict.resolved = True
    conflict.description = f"[resolved:{body.resolution}] {conflict.description or ''}"
    return conflict


@router.post("/{conflict_id}/merge", response_model=ConflictMergeResponse)
async def merge_conflict(
    conflict_id: UUID,
    body: ConflictMerge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConflictMergeResponse:
    """Apply selected fields from the thread update into the surviving task.

    Only valid for ``scope="thread_update"`` conflicts that reference both
    tasks. The OLDER task survives (keeps identity, calendar_event_id,
    confirmed status); the NEWER task supplies the chosen field values and is
    then dismissed. The surviving task's prior state is snapshotted into
    ``previous_revision`` (same shape as the dedupe auto-supersede path) so the
    change is auditable/revertible.
    """
    stmt = select(Conflict).where(Conflict.id == conflict_id, Conflict.user_id == current_user.id)
    conflict = (await db.execute(stmt)).scalar_one_or_none()
    if not conflict:
        raise HTTPException(
            status_code=404, detail={"code": "CONFLICT_NOT_FOUND", "message": "Conflict not found"}
        )
    if conflict.resolved:
        raise HTTPException(
            status_code=409, detail={"code": "ALREADY_RESOLVED", "message": "Conflict already resolved"}
        )
    if conflict.scope != "thread_update":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MERGE_SCOPE_UNSUPPORTED",
                "message": "Field merge is only available for thread_update conflicts. "
                "Use accept_a / accept_b / dismiss for other scopes.",
            },
        )
    task_ids = list(conflict.task_ids or [])
    if len(task_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MERGE_MISSING_TASKS",
                "message": "Conflict does not reference two tasks to merge.",
            },
        )

    tasks_stmt = select(Task).where(Task.id.in_(task_ids), Task.user_id == current_user.id)
    tasks = list((await db.execute(tasks_stmt)).scalars().all())
    if len(tasks) < 2:
        raise HTTPException(
            status_code=400,
            detail={"code": "MERGE_MISSING_TASKS", "message": "One or both tasks no longer exist."},
        )
    # Older task survives; newer task is the update source. created_at is the
    # robust signal — positional task_ids ordering is an implementation detail
    # of the pipeline and shouldn't leak into resolution semantics.
    tasks.sort(key=lambda t: t.created_at)
    survivor, source = tasks[0], tasks[-1]

    survivor.previous_revision = {
        "title": survivor.title,
        "description": survivor.description,
        "assignee": survivor.assignee,
        "deadline": survivor.deadline.isoformat() if survivor.deadline else None,
        "deadline_v2": survivor.deadline_v2,
        "priority": survivor.priority,
        "uncertainty": survivor.uncertainty,
        "source_doc_id": str(survivor.source_doc_id) if survivor.source_doc_id else None,
        "updated_at": survivor.updated_at.isoformat()
        if hasattr(survivor.updated_at, "isoformat")
        else str(survivor.updated_at),
    }
    for field in body.fields:
        setattr(survivor, field, getattr(source, field))
    survivor.updated_at = datetime.now(timezone.utc)

    source.status = "dismissed"
    source.updated_at = datetime.now(timezone.utc)

    conflict.resolved = True
    conflict.description = f"[merged:thread_update] {conflict.description or ''}"

    # Calendar resync only when the surviving task actually has a calendar event
    # AND the merge touched a field the calendar reflects (title/deadline).
    # Otherwise there's nothing to update — never create a surprise event.
    calendar_reflected = {"title", "deadline"} & set(body.fields)
    access_token: str | None = None
    if not survivor.calendar_event_id:
        cal_info = CalendarSyncInfo(
            status="skipped", reason="no_calendar_event",
            message="No calendar event to update.",
        )
    elif not calendar_reflected:
        cal_info = CalendarSyncInfo(
            status="skipped", reason="no_calendar_change",
            message="No calendar-relevant field changed.",
        )
    else:
        access_token, cal_info = await _build_calendar_resync_payload(current_user)

    # Persist task/conflict mutations (and any token refresh) BEFORE enqueuing,
    # so the agent's resync job reads committed data, not a half-applied state.
    await db.commit()

    if access_token:
        settings = get_settings()
        redis_client = await get_redis()
        await redis_client.rpush(
            settings.pipeline_queue_name,
            json.dumps(
                {
                    "source_type": "calendar_resync",
                    "user_id": str(current_user.id),
                    "access_token": access_token,
                    "task_id": str(survivor.id),
                    "triggered_by": "conflict_merge",
                }
            ),
        )

    return ConflictMergeResponse(
        merged_task_id=survivor.id,
        dismissed_task_id=source.id,
        calendar_sync=cal_info,
    )
