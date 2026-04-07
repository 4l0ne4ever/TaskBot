from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: str
    last_sync_at: datetime | None
    status: str
    error_message: str | None


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_doc_id: UUID | None
    status: str
    tasks_extracted: int
    conflicts_found: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
