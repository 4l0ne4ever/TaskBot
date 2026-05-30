import uuid
from datetime import date, time

from sqlalchemy import ARRAY, Boolean, Date, DateTime, ForeignKey, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_canonical: Mapped[str | None] = mapped_column(Text, nullable=True, index=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Round 13 (2026-05-31): time-of-day component when the email/doc says it.
    # Stored separately so existing date-only logic (sort, filter, conflict
    # comparison) keeps working without coalescing nulls. Frontend renders
    # "YYYY-MM-DD HH:MM" when set, "YYYY-MM-DD" otherwise.
    deadline_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    deadline_v2: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertainty: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    calendar_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_revision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
