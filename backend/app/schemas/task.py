from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    assignee: str | None
    deadline: date | None
    priority: str | None
    status: str
    missing_fields: list[str] | None
    calendar_event_id: str | None
    notification_sent: bool
    source_doc_id: UUID | None
    source_type: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskUpdate(BaseModel):
    title: str | None = None
    assignee: str | None = None
    deadline: date | None = None
    priority: str | None = None
    status: str | None = Field(None, pattern=r"^(pending|confirmed|dismissed)$")
