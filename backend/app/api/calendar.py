import json
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.redis import get_redis
from app.models.task import Task
from app.models.user import User
from app.schemas.calendar import CalendarEvent, CalendarEventCreate, CalendarEventUpdate

router = APIRouter()


@router.get("/events", response_model=list[CalendarEvent])
async def list_events(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    # Recurring tasks whose anchor (``deadline``) is BEFORE the visible window
    # must still be returned — the client expands the RRULE forward and may
    # render occurrences inside [start, end]. Non-recurring tasks keep the
    # narrow "anchor falls inside window" rule. Both halves share the
    # ``deadline <= end`` upper bound: an anchor in the future can't expand
    # backward into the past.
    stmt = (
        select(Task)
        .where(Task.user_id == current_user.id, Task.deadline.isnot(None))
        .order_by(Task.deadline.asc())
    )
    if end:
        stmt = stmt.where(Task.deadline <= end)
    if start:
        stmt = stmt.where(
            or_(
                Task.deadline >= start,
                Task.recurrence_rule.isnot(None),
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/resync_all", status_code=202)
async def resync_all_to_google(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Force-enqueue a Google Calendar sync job for every confirmed task with
    a deadline.

    The pipeline's ``dispatch_notifications`` uses ``task.calendar_event_id``
    to UPDATE existing events and CREATE missing ones, so re-running it on
    already-synced tasks is idempotent — no duplicates.

    Designed for the "Sync now" button on /calendar when the user knows
    something drifted (manual edits in Google Calendar, network skip, etc.)
    or wants visible confirmation that the calendar matches the task list.
    """
    from app.api.conflicts import _build_calendar_resync_payload

    stmt = select(Task).where(
        Task.user_id == current_user.id,
        Task.status == "confirmed",
        Task.deadline.isnot(None),
    )
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    if not tasks:
        return {"queued": 0}

    access_token, _ = await _build_calendar_resync_payload(current_user)
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail={"code": "CALENDAR_TOKEN_MISSING", "message": "Reconnect Google to sync the calendar."},
        )

    settings = get_settings()
    redis_client = await get_redis()
    for task in tasks:
        await redis_client.rpush(
            settings.pipeline_queue_name,
            json.dumps(
                {
                    "source_type": "calendar_resync",
                    "user_id": str(current_user.id),
                    "access_token": access_token,
                    "task_id": str(task.id),
                    "triggered_by": "manual_resync_all",
                }
            ),
        )
    return {"queued": len(tasks)}


@router.post("/events", response_model=CalendarEvent, status_code=201)
async def create_event(
    body: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = Task(
        id=uuid4(),
        user_id=current_user.id,
        title=body.title,
        assignee=body.assignee,
        deadline=body.deadline,
        priority=body.priority or "medium",
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/events/{event_id}", response_model=CalendarEvent)
async def update_event(
    event_id: UUID,
    body: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == event_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Event not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    result = await db.execute(
        select(Task).where(Task.id == event_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(task)
    await db.commit()
    return {"deleted": str(event_id)}
