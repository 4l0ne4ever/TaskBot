"""Relationship model — typed edges between entities (and entity → task).

XOR target invariant (enforced by DB CHECK constraint
``ck_relationships_target_xor``): exactly one of ``to_entity_id`` or
``to_task_id`` is non-null. Each edge points to *either* another entity or a
task — never both, never neither. This keeps graph-traversal queries
unambiguous.

Initial relationship_type set (open; field is plain TEXT so new types do
not need a migration):
  - 'assigned_to'        : person  → task    (from task.assignee_canonical)
  - 'mentioned_in'       : entity  → task    (from task description / evidence)
  - 'collaborates_with'  : person  → person  (co-occurrence in source_doc)

Planned for Phase 2+ (heuristic-derived, not implemented yet):
  - 'depends_on', 'blocks', 'related_to'

Confidence is nullable: NULL means "not tracked" (entity was derived from
deterministic rules with no score), which is semantically different from
``0.0`` meaning "tracked with zero confidence".
"""
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
    )
    to_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "(to_entity_id IS NOT NULL) <> (to_task_id IS NOT NULL)",
            name="ck_relationships_target_xor",
        ),
        Index("ix_relationships_user_from", "user_id", "from_entity_id"),
        Index("ix_relationships_user_to_entity", "user_id", "to_entity_id"),
        Index("ix_relationships_user_to_task", "user_id", "to_task_id"),
        Index("ix_relationships_source_doc", "source_doc_id"),
    )
