from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalendarEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    assignee: str | None
    deadline: date | None
    # ``deadline_time`` lets the UI render timed events distinct from all-day
    # ones; ``recurrence_rule`` lets the UI expand a recurring task into one
    # chip per occurrence inside the visible month (mirroring Google Calendar
    # behaviour). Both default to NULL for legacy single-day events.
    deadline_time: time | None = None
    recurrence_rule: str | None = None
    priority: str | None
    status: str
    calendar_event_id: str | None
    source_doc_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    assignee: str | None = None
    deadline: date | None = None
    priority: str | None = None
    status: str | None = Field(None, pattern=r"^(pending|confirmed|dismissed)$")


class CalendarEventCreate(BaseModel):
    title: str
    assignee: str | None = None
    deadline: date
    priority: str | None = Field("medium", pattern=r"^(high|medium|low)$")
