import json
import re
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as _delete, select, update as _update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskResponse, TaskSourceResponse, TaskUpdate

_MAX_EXCERPT_CHARS = 600
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_WS_RE = re.compile(r"[ \t]{2,}")
_CRLF_RE = re.compile(r"\r\n?")


def _clean_excerpt(raw: str | None) -> str | None:
    if not raw:
        return None
    text = _HTML_TAG_RE.sub(" ", raw)
    text = _CRLF_RE.sub("\n", text)
    text = _MULTI_WS_RE.sub(" ", text).strip()
    if len(text) > _MAX_EXCERPT_CHARS:
        text = text[:_MAX_EXCERPT_CHARS].rstrip() + "…"
    return text or None

router = APIRouter()


async def _source_type_by_doc_id(db: AsyncSession, doc_ids: list[UUID]) -> dict[UUID, str]:
    if not doc_ids:
        return {}
    r = await db.execute(
        select(SourceDocument.id, SourceDocument.source_type).where(SourceDocument.id.in_(doc_ids))
    )
    return {row[0]: row[1] for row in r.all()}


def _task_response(task: Task, source_type: str | None) -> TaskResponse:
    data = TaskResponse.model_validate(task).model_dump()
    data["source_type"] = source_type
    if not get_settings().task_v2_read_enabled:
        data["deadline_v2"] = None
        data["uncertainty"] = None
    return TaskResponse.model_validate(data)


async def _enrich_tasks(db: AsyncSession, tasks: list[Task]) -> list[TaskResponse]:
    doc_ids = [t.source_doc_id for t in tasks if t.source_doc_id]
    mapping = await _source_type_by_doc_id(db, doc_ids)
    return [
        _task_response(
            t,
            mapping.get(t.source_doc_id) if t.source_doc_id else None,
        )
        for t in tasks
    ]


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = Query(None, pattern=r"^(pending|confirmed|dismissed)$"),
    source: str | None = Query(None, pattern=r"^(gmail|drive|upload)$"),
    deadline_from: date | None = Query(None),
    deadline_to: date | None = Query(None),
    sort: str = Query("created_desc", pattern=r"^(deadline_asc|created_desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskResponse]:
    stmt = select(Task).where(Task.user_id == current_user.id)

    if status:
        stmt = stmt.where(Task.status == status)
    if deadline_from:
        stmt = stmt.where(Task.deadline >= deadline_from)
    if deadline_to:
        stmt = stmt.where(Task.deadline <= deadline_to)
    if source:
        stmt = stmt.join(SourceDocument, Task.source_doc_id == SourceDocument.id).where(
            SourceDocument.source_type == source
        )

    if sort == "deadline_asc":
        stmt = stmt.order_by(Task.deadline.asc().nulls_last(), Task.created_at.desc())
    else:
        stmt = stmt.order_by(Task.created_at.desc())

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    return await _enrich_tasks(db, tasks)


@router.get("/source-by-ref", response_model=TaskSourceResponse)
async def get_source_by_ref(
    ref: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskSourceResponse:
    """Look up a source document by its pipeline source_ref string.

    Used by the conflict UI when a conflict row has no task_ids — the
    source_a_ref / source_b_ref values are matched directly against
    source_documents.source_ref. Registered before ``/{task_id}`` so the
    static path isn't captured by the UUID path parameter.
    """
    stmt = select(SourceDocument).where(
        SourceDocument.source_ref == ref,
        SourceDocument.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_NOT_FOUND", "message": "Source document not found"})
    return TaskSourceResponse(
        source_type=doc.source_type,
        source_ref=doc.source_ref,
        excerpt=_clean_excerpt(doc.raw_text),
        created_at=doc.created_at,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})
    enriched = await _enrich_tasks(db, [task])
    return enriched[0]


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(task, field, value)
    if changes:
        task.updated_at = datetime.now(timezone.utc)

    # confirmed_by is controlled server-side — the client only sends status.
    if changes.get("status") == "confirmed":
        task.confirmed_by = "user"
    elif changes.get("status") == "pending":
        task.confirmed_by = None  # intentional revert clears badge signal

    # When confirming a task that has a deadline, enqueue a calendar event
    # creation/update job so the event appears without requiring a full sync.
    need_calendar = changes.get("status") == "confirmed" and task.deadline is not None
    access_token: str | None = None
    if need_calendar:
        from app.api.conflicts import _build_calendar_resync_payload
        access_token, _ = await _build_calendar_resync_payload(current_user)

    enriched = await _enrich_tasks(db, [task])

    # Commit before enqueue so the agent reads the confirmed task, not stale state.
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
                    "task_id": str(task.id),
                    "triggered_by": "task_confirm",
                }
            ),
        )

    return enriched[0]


@router.delete("")
async def delete_tasks_bulk(
    status: str | None = Query(None, pattern=r"^(pending|confirmed|dismissed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    stmt = _delete(Task).where(Task.user_id == current_user.id)
    if status:
        stmt = stmt.where(Task.status == status)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount}


@router.get("/{task_id}/source", response_model=TaskSourceResponse)
async def get_task_source(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskSourceResponse:
    task_stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    task_result = await db.execute(task_stmt)
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})
    if not task.source_doc_id:
        raise HTTPException(status_code=404, detail={"code": "NO_SOURCE", "message": "Task has no source document"})

    doc_stmt = select(SourceDocument).where(
        SourceDocument.id == task.source_doc_id,
        SourceDocument.user_id == current_user.id,
    )
    doc_result = await db.execute(doc_stmt)
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_NOT_FOUND", "message": "Source document not found"})

    return TaskSourceResponse(
        source_type=doc.source_type,
        source_ref=doc.source_ref,
        excerpt=_clean_excerpt(doc.raw_text),
        created_at=doc.created_at,
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})

    calendar_event_id = task.calendar_event_id
    await db.delete(task)
    return {"deleted": str(task_id), "calendar_event_id": calendar_event_id or ""}
