"""Add assignee_canonical column to tasks

Revision ID: 0007_tasks_assignee_canonical
Revises: 0006_sourcedocs_uniq_ref
Create Date: 2026-05-10

Background (Q-05):

The pipeline's AssigneeResolver resolves raw LLM assignee strings to a
canonical form via a per-user pool (Redis-backed). The canonical form is
what downstream deduplication, grouping, and search should use, but
previously it was only carried in-memory through the pipeline dict — it
was never persisted to the DB. This meant every UI feature that wanted
to group tasks by assignee was forced to rely on the raw LLM string,
which varies wildly for the same person ("Bạn Hương", "Hương", "c.Hương"
etc.).

Migration:

    1. ADD COLUMN tasks.assignee_canonical TEXT NULLABLE — stores the
       canonical form as computed by AssigneeResolver at save time.
       NULL for rows created before this migration; can be backfilled
       separately when the canonical pool is available.
    2. CREATE INDEX on (user_id, assignee_canonical) — enables efficient
       grouping queries ("show me all tasks assigned to X").

The column is intentionally nullable: legacy rows can live alongside new
rows without a forced backfill, and callers must handle NULL (treat it
as "canonical unknown, fall back to assignee").
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_tasks_assignee_canonical"
down_revision = "0006_sourcedocs_uniq_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("assignee_canonical", sa.Text(), nullable=True))
    op.create_index(
        "ix_tasks_user_assignee_canonical",
        "tasks",
        ["user_id", "assignee_canonical"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_user_assignee_canonical", table_name="tasks")
    op.drop_column("tasks", "assignee_canonical")
