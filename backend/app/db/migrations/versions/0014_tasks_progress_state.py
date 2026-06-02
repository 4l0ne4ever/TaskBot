"""Add tasks.progress_state column.

Revision ID: 0014_tasks_progress_state
Revises: 0013_tasks_deadline_time
Create Date: 2026-06-02

Phase 4 (no-deadline UX, 2026-06-02): introduces a Google-Tasks-like
"tracking" column so users can mark progress on tasks that lack a
deadline — todo / in_progress / done. Orthogonal to ``status``
(pending/confirmed/dismissed), which represents lifecycle/triage. Anna's
ask: "kế thừa các tính năng quan trọng chính của google task là được"
(give me Google Tasks' core tracking semantics inside TaskBot — no
external sync).

Nullable + no default: legacy rows stay NULL, the UI treats NULL as
"todo". A non-null default would write to every existing row at the
migration boundary, which we don't need.
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_tasks_progress_state"
down_revision = "0013_tasks_deadline_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("progress_state", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "progress_state")
