"""Add tasks.confirmed_by column

Revision ID: 0011_tasks_confirmed_by
Revises: 0010_tasks_evidence_quote
Create Date: 2026-05-21

Background (Phase 7.2 — Auto-confirm + Phase 7.3 — Confirm Gates):

Tracks HOW a task reached confirmed status so the UI can distinguish
between explicit user confirmation ("user") and pipeline-driven
auto-confirmation ("system"), and so the system can expose a "Revert"
action only on auto-confirmed tasks.

Values:
    NULL           — task has never been confirmed (pending/dismissed)
    "user"         — confirmed by an explicit PATCH /tasks/{id} call
    "system"       — auto-confirmed by the save_tasks pipeline node when
                     the pipeline's calibration bands (uncertainty IS NULL)
                     + no intra-batch conflict + actionable fields
                     (deadline OR assignee) all pass

The column also doubles as a badge signal: status="pending" + confirmed_by
IS NOT NULL means the task was previously confirmed but the pipeline
superseded it (7.3b reset). The UI shows "Updated since confirmed" so Anna
knows to re-review. On revert (PATCH status=pending by the user), the
backend clears confirmed_by=NULL — the badge should not appear after an
intentional revert.

Migration:
    ALTER TABLE tasks ADD COLUMN confirmed_by TEXT NULL.

No index, no backfill — reasoning identical to evidence_quote (0010): the
column is always read alongside the task row, not filtered in isolation.
Existing rows stay NULL, which the UI treats as "never confirmed".
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_tasks_confirmed_by"
down_revision = "0010_tasks_evidence_quote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("confirmed_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "confirmed_by")
