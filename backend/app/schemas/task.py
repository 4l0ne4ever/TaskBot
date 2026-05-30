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
    evidence_quote: str | None = None
    confirmed_by: str | None = None
    source_doc_id: UUID | None
    source_type: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskSourceResponse(BaseModel):
    source_type: str
    source_ref: str
    excerpt: str | None
    created_at: datetime
    # When the email/file was originally received (parsed from Gmail Date:
    # header for emails; null for Drive files until file modifiedTime is
    # wired). Frontend prefers this over created_at for display when set.
    received_at: datetime | None = None


class TeamMemberStats(BaseModel):
    """Per-assignee workload + risk rollup for the Team View (Phase 8.2).

    ``assignee`` is the canonical name (falls back to the raw assignee string,
    or ``null`` for the unassigned bucket). Counts exclude dismissed tasks
    except where noted.
    """

    assignee: str | None
    open: int            # not dismissed
    pending: int
    confirmed: int
    overdue: int         # deadline < today, not dismissed
    due_this_week: int   # today <= deadline <= today+7, not dismissed
    in_conflict: int     # appears in an unresolved conflict
    needs_review: int    # pending and never confirmed (confirmed_by is null)


class TeamView(BaseModel):
    members: list[TeamMemberStats]
    unassigned: TeamMemberStats


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee: str | None = None
    deadline: date | None = None
    deadline_v2: TaskDeadlineV2 | None = None
    priority: str | None = None
    uncertainty: TaskUncertainty | None = None
    status: str | None = Field(None, pattern=r"^(pending|confirmed|dismissed)$")
