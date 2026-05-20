from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conflict_type: str
    description: str | None
    source_a_ref: str | None
    source_b_ref: str | None
    task_ids: list[UUID] | None
    scope: str | None
    resolved: bool
    created_at: datetime


class ConflictResolve(BaseModel):
    resolution: str = Field(..., pattern=r"^(accept_a|accept_b|dismiss)$")


# Fields the user may carry over from the thread update into the surviving task.
# Excludes status/calendar_event_id/identity columns — merge only touches
# the user-facing content fields that can legitimately differ across a thread.
MERGEABLE_FIELDS: frozenset[str] = frozenset(
    {"title", "description", "assignee", "deadline", "priority"}
)


class ConflictMerge(BaseModel):
    fields: list[str] = Field(..., min_length=1)

    @field_validator("fields")
    @classmethod
    def _validate_fields(cls, v: list[str]) -> list[str]:
        unknown = [f for f in v if f not in MERGEABLE_FIELDS]
        if unknown:
            raise ValueError(
                f"unmergeable field(s): {unknown}. Allowed: {sorted(MERGEABLE_FIELDS)}"
            )
        # de-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for f in v:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out


class CalendarSyncInfo(BaseModel):
    status: str  # "skipped" | "queued" | "failed"
    reason: str | None = None
    message: str


class ConflictMergeResponse(BaseModel):
    merged_task_id: UUID
    dismissed_task_id: UUID
    calendar_sync: CalendarSyncInfo
