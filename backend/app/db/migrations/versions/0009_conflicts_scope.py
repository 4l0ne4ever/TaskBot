"""Add conflicts.scope column

Revision ID: 0009_conflicts_scope
Revises: 0008_entity_graph
Create Date: 2026-05-19

Background (Phase A' wrap + Phase 2.3 prep):

The conflict-detection pipeline emits records carrying a runtime ``scope``
field with one of four values:
  - ``intra_batch``    — two tasks emitted from the same source batch (Phase 2.1)
  - ``thread_update``  — a thread-update marker promoted the conflict
                          (Phase 2.1 intra-batch path + Phase A' inter-doc path)
  - ``inter_doc``      — generic cross-document conflict, no marker (Phase A')
  - ``multi_source``   — cross-platform Gmail ↔ Drive conflict (Phase 2.2)

Until now ``scope`` lived only in-memory in ``state["conflicts"]``;
``save_tasks_service`` discarded it on persist. Phase 2.3 (Frontend
conflict resolution UI) needs scope for badge rendering and for
differentiated resolution flows, so the column has to exist before the UI
work begins.

Migration:
    1. ALTER TABLE conflicts ADD COLUMN scope TEXT NULL — open-set TEXT,
       no CHECK constraint. The enum is enforced at the application layer;
       keeping the DB column open avoids a migration every time a new
       scope is added. Existing rows stay NULL — they pre-date scope
       tagging; backfill is out of scope (and not safely possible without
       re-running the pipeline, which would change other fields too).

    2. CREATE INDEX ix_conflicts_scope (partial: WHERE scope IS NOT NULL).
       During the bootstrap window most rows are still NULL; a partial
       index keeps the index small and avoids indexing the pre-existing
       NULL backlog. The Phase 2.3 UI will filter by scope on the
       conflict-resolution page — without this index that page would
       full-scan. Using ``WHERE scope IS NOT NULL`` rather than a scope
       value list means no migration is required when a new scope name
       lands in the application.

Wiring of ``save_tasks_service`` to actually write the column is deferred
to Phase 2.3 — this migration only adds the column. Until 2.3 ships, the
column will remain NULL for newly-persisted conflicts too. That separation
is intentional: it lets 2.3 land in isolation without bundling a schema
change into the same commit.
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_conflicts_scope"
down_revision = "0008_entity_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conflicts", sa.Column("scope", sa.Text(), nullable=True))
    op.create_index(
        "ix_conflicts_scope",
        "conflicts",
        ["scope"],
        postgresql_where=sa.text("scope IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_conflicts_scope", table_name="conflicts")
    op.drop_column("conflicts", "scope")
