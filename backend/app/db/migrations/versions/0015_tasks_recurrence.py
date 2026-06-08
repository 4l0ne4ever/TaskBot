"""Add tasks.recurrence_rule, recurrence_suggested, recurrence_dismissed_at.

Revision ID: 0015_tasks_recurrence
Revises: 0014_tasks_progress_state
Create Date: 2026-06-03

Phase 6.6 (recurring events, 2026-06-03): three nullable columns implement
the LLM-suggest / user-confirm pattern for recurring tasks.

- ``recurrence_rule``        — active RFC 5545 RRULE string (drives the
  Google Calendar recurring event). NULL = task is one-shot.
- ``recurrence_suggested``   — LLM-detected RRULE awaiting user confirm.
  Surfaced in the pending-review card with an "Apply" button. Cleared on
  apply (copied to ``recurrence_rule``) or on dismiss.
- ``recurrence_dismissed_at``— UTC timestamp of dismissal. Suppresses
  re-suggestion on re-sync of the same task (the dismiss is a task-level
  intent, not an email-level one). Also useful for future analytics.

All nullable, no defaults: legacy rows stay NULL, no rewrite at the
migration boundary.
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_tasks_recurrence"
down_revision = "0014_tasks_progress_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("recurrence_rule", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("recurrence_suggested", sa.Text(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("recurrence_dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "recurrence_dismissed_at")
    op.drop_column("tasks", "recurrence_suggested")
    op.drop_column("tasks", "recurrence_rule")
