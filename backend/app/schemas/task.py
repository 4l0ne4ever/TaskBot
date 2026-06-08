from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.recurrence import RecurrenceError, validate_rrule


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
    # Round 13 (2026-05-31): time-of-day component (e.g. "3:00 PM" → 15:00:00)
    # extracted from the email's verbatim deadline phrase. Null when the
    # source doesn't specify a time — frontend then renders date-only.
    deadline_time: time | None = None
    deadline_v2: TaskDeadlineV2 | None = None
    priority: str | None
    uncertainty: TaskUncertainty | None = None
    status: str
    missing_fields: list[str] | None
    calendar_event_id: str | None
    notification_sent: bool
    evidence_quote: str | None = None
    confirmed_by: str | None = None
    # Phase 4 (no-deadline UX): Google-Tasks-like tracking state. Null in the
    # API response means "todo" — the frontend defaults it for legacy rows.
    progress_state: str | None = None
    # Phase 6.6 (recurring events): see backend/app/utils/recurrence.py for
    # the whitelist contract. recurrence_rule = active; recurrence_suggested
    # = LLM-detected awaiting confirm; recurrence_dismissed_at = suppress flag.
    recurrence_rule: str | None = None
    recurrence_suggested: str | None = None
    recurrence_dismissed_at: datetime | None = None
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
    deadline_time: time | None = None  # Round 13: editable time-of-day
    deadline_v2: TaskDeadlineV2 | None = None
    priority: str | None = None
    uncertainty: TaskUncertainty | None = None
    status: str | None = Field(None, pattern=r"^(pending|confirmed|dismissed)$")
    # Phase 4 — pattern-matched so a typo can't silently land in the column.
    progress_state: str | None = Field(None, pattern=r"^(todo|in_progress|done)$")
    # Phase 6.6 — recurring events. Empty string sentinel means "clear" (used
    # by the Remove recurrence flow on the frontend). Any non-empty value goes
    # through the whitelist validator and is canonicalized in place.
    recurrence_rule: str | None = None
    # Dismiss the suggested recurrence (UI sends ``true`` to set the timestamp
    # to now; backend ignores ``false``). Not a raw timestamp field because
    # we don't want clients to backdate it.
    dismiss_recurrence_suggestion: bool | None = None

    @field_validator("recurrence_rule")
    @classmethod
    def _validate_rrule(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        try:
            return validate_rrule(v)
        except RecurrenceError as exc:
            raise ValueError(str(exc)) from exc
