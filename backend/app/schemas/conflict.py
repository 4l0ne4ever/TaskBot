from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conflict_type: str
    description: str | None
    source_a_ref: str | None
    source_b_ref: str | None
    task_ids: list[UUID] | None
    resolved: bool
    created_at: datetime


class ConflictResolve(BaseModel):
    resolution: str = Field(..., pattern=r"^(accept_a|accept_b|dismiss)$")
