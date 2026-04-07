from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskResponse, TaskUpdate

router = APIRouter()


async def _source_type_by_doc_id(db: AsyncSession, doc_ids: list[UUID]) -> dict[UUID, str]:
    if not doc_ids:
        return {}
    r = await db.execute(
        select(SourceDocument.id, SourceDocument.source_type).where(SourceDocument.id.in_(doc_ids))
    )
    return {row[0]: row[1] for row in r.all()}


def _task_response(task: Task, source_type: str | None) -> TaskResponse:
    return TaskResponse.model_validate(task).model_copy(update={"source_type": source_type})


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

    enriched = await _enrich_tasks(db, [task])
    return enriched[0]


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
