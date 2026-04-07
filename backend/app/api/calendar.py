from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
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
    stmt = (
        select(Task)
        .where(Task.user_id == current_user.id, Task.deadline.isnot(None))
        .order_by(Task.deadline.asc())
    )
    if start:
        stmt = stmt.where(Task.deadline >= start)
    if end:
        stmt = stmt.where(Task.deadline <= end)
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
