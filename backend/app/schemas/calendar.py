from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalendarEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    assignee: str | None
    deadline: date | None
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
