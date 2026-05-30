import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_group_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # When the email was actually received by Google (parsed from the Date:
    # header or the message's internalDate). Distinct from created_at, which
    # is when TaskBot synced it. Nullable because Drive sync doesn't populate
    # this yet (file modifiedTime is a defensible analog but is future work).
    received_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_source_documents_user_source_ref",
            "user_id",
            "source_type",
            "source_ref",
            unique=True,
        ),
    )
