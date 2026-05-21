"""Add tasks.evidence_quote column

Revision ID: 0010_tasks_evidence_quote
Revises: 0009_conflicts_scope
Create Date: 2026-05-20

Background (Phase 7.1 — Evidence Highlighting):

The extraction pipeline already produces a per-task ``evidence_quote`` — a
verbatim substring copied from the source text that supports the task
(``prompts.py``). It is normalized (``normalize_tasks``) and *validated*: the
validate node rejects (abstains) any task whose quote can't be located in the
source text (``validate_tasks._evidence_quote_invalid``). So when a quote
survives to persist, it is guaranteed to appear verbatim in the source —
which makes exact (not fuzzy) highlighting possible in the UI.

Until now the quote was discarded at persist time: ``save_tasks_service``
forwarded it only into the transient entity-graph payload, never onto the
``tasks`` row. Phase 7.1 surfaces it in the task detail / conflict source
panel (highlighting the quote inside the source excerpt), so the column has
to exist before that UI work.

Migration:
    ALTER TABLE tasks ADD COLUMN evidence_quote TEXT NULL.

No index: the column is only ever read alongside its task row (by id), never
filtered or joined on, so an index would be dead weight.

No backfill: existing rows pre-date persistence and stay NULL. The frontend
falls back to the plain source excerpt when the quote is NULL, so old tasks
degrade gracefully. Backfilling would require re-running the pipeline (which
would also rewrite other fields) — out of scope; fresh syncs populate it
going forward. ``save_tasks_service`` is wired to write the column in the
same Phase 7.1 change set (both the create and the update-in-place reuse
paths, so a re-extracted task refreshes its quote rather than keeping a
stale one).
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_tasks_evidence_quote"
down_revision = "0009_conflicts_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("evidence_quote", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "evidence_quote")
