"""Entity model — first-class representation of people / projects / topics.

Tasks have raw assignee strings and source document references but no
structured representation of the entities involved across documents. The
entity graph layer (added in migration 0008) provides this so the pipeline
can detect multi-source conflicts by entity-set intersection, the UI can
render a graph view, and downstream features (digest grouping, graph
queries) get a shared substrate.

``canonical_name`` follows the same data-driven principle as
``app.services.assignee_resolver`` — no hardcoded honorific list; the user's
observed forms become the source of truth.

Entity types (open set; field is plain TEXT so new types do not need a
migration):
  - 'person'  — a human assignee or collaborator
  - 'project' — a long-running deliverable or initiative
  - 'topic'   — a recurring theme (extracted from task titles / descriptions)
"""
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # NOTE: column is `entity_metadata` (not `metadata`) because SQLAlchemy
    # reserves `Base.metadata` for the schema-level MetaData object — a
    # `metadata` attribute on a Declarative class would shadow it and break
    # autogeneration / reflection.
    entity_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entity_type",
            "canonical_name",
            name="uq_entities_user_type_canonical",
        ),
        Index("ix_entities_user_id", "user_id"),
        Index("ix_entities_user_type", "user_id", "entity_type"),
    )
