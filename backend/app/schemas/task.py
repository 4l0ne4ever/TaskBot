from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskUncertainty(BaseModel):
    type: str | None = None
    reason: str | None = None


class TaskDeadlineV2(BaseModel):
    type: str | None = None
    iso: str | None = None
    start: str | None = None
    end: str | None = None
    text: str | None = None
    resolved_from: str | None = None
    confidence: float | None = None
    source: str | None = None
    is_ambiguous: bool | None = None
    suggested_iso: str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    assignee: str | None
    deadline: date | None
    deadline_v2: TaskDeadlineV2 | None = None
    priority: str | None
    uncertainty: TaskUncertainty | None = None
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
    description: str | None = None
    assignee: str | None = None
    deadline: date | None = None
    deadline_v2: TaskDeadlineV2 | None = None
    priority: str | None = None
    uncertainty: TaskUncertainty | None = None
    status: str | None = Field(None, pattern=r"^(pending|confirmed|dismissed)$")
