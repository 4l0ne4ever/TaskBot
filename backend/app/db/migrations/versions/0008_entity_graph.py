"""Add entity_graph: entities + relationships tables

Revision ID: 0008_entity_graph
Revises: 0007_tasks_assignee_canonical
Create Date: 2026-05-18

Background (Goal #2 — Entity graph for conflict-detection and visualization):

The pipeline produces tasks with raw assignee strings and source provenance,
but tasks live in flat rows — there is no first-class representation of the
*people / projects / topics* across documents, or the *relationships* between
them. Without this layer:
  - Multi-source conflict detection (Phase 2.2) cannot ask "who else does this
    task involve?" without re-scanning every task row.
  - The visualization layer (Phase 3) has nothing structured to render.
  - Future features (digest grouping, cross-task graph queries) re-invent the
    wheel on every endpoint.

Migration:

    1. CREATE TABLE entities — per-user (person|project|topic, …).
       canonical_name is the data-driven canonical form (reuses the principle
       from app.services.assignee_resolver — no hardcoded honorific list, the
       user's observed forms become the source of truth).
       aliases JSONB captures raw forms observed for the entity (for UI
       "also known as" display).
       entity_metadata JSONB is intentionally schema-free; columns are added
       only when accessed through indexed queries.
       UNIQUE (user_id, entity_type, canonical_name) prevents duplicates.

    2. CREATE TABLE relationships — typed edges. XOR target ensures each row
       points to *either* another entity or a task, not both.
         - CASCADE on entity/task delete: when the endpoint goes away the edge
           loses meaning, so dangling rows would only be debug noise.
         - SET NULL on source_doc_id delete: provenance is lost but the edge
           itself stays valid (the relationship was observed at some point;
           the document just isn't around to cite).

    3. Indexes on (user_id, from_entity_id), (user_id, to_entity_id),
       (user_id, to_task_id), and source_doc_id for graph traversal and
       provenance lookups under tenant isolation.

Design deferrals (documented for future migrations, do NOT add now):
  - canonical_name normalisation column (lowercased / diacritic-folded) with
    hash index — added only if Phase 1.2 benchmark shows entity lookup p95
    > 50 ms on real data. Premature optimisation avoided per assignee_resolver
    pattern (scan + score is acceptable at ~100s entities/user).
  - relationship_type stays plain TEXT (open set). Initial pipeline emits
    'assigned_to', 'mentioned_in', 'collaborates_with'. Future expansion:
    'depends_on', 'blocks', 'related_to' (heuristic-derived in Phase 2+).
    Open set means no migration is needed when adding new types.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_entity_graph"
down_revision = "0007_tasks_assignee_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("entity_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "entity_type",
            "canonical_name",
            name="uq_entities_user_type_canonical",
        ),
    )
    op.create_index("ix_entities_user_id", "entities", ["user_id"])
    op.create_index("ix_entities_user_type", "entities", ["user_id", "entity_type"])

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "from_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "to_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "source_doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(to_entity_id IS NOT NULL) <> (to_task_id IS NOT NULL)",
            name="ck_relationships_target_xor",
        ),
    )
    op.create_index(
        "ix_relationships_user_from",
        "relationships",
        ["user_id", "from_entity_id"],
    )
    op.create_index(
        "ix_relationships_user_to_entity",
        "relationships",
        ["user_id", "to_entity_id"],
    )
    op.create_index(
        "ix_relationships_user_to_task",
        "relationships",
        ["user_id", "to_task_id"],
    )
    op.create_index(
        "ix_relationships_source_doc",
        "relationships",
        ["source_doc_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationships_source_doc", table_name="relationships")
    op.drop_index("ix_relationships_user_to_task", table_name="relationships")
    op.drop_index("ix_relationships_user_to_entity", table_name="relationships")
    op.drop_index("ix_relationships_user_from", table_name="relationships")
    op.drop_table("relationships")
    op.drop_index("ix_entities_user_type", table_name="entities")
    op.drop_index("ix_entities_user_id", table_name="entities")
    op.drop_table("entities")
