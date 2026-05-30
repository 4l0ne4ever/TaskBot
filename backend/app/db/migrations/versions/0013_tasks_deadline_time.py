"""Add tasks.deadline_time column.

Revision ID: 0013_tasks_deadline_time
Revises: 0012_src_docs_received_at
Create Date: 2026-05-31

Round 13 (2026-05-31): the email body often carries a time-of-day alongside
the date ("Friday, 20 June 2026, 3:00 PM ICT"), but ``tasks.deadline`` is
``DATE`` so the time was being silently dropped. Storing it lets the UI
show the full deadline (Anna doesn't have to open the source email to know
*when* during the day), and lets the Google Calendar dispatch create a
timed event instead of an all-day event when a time is known.

Nullable so every existing row stays valid — missing time renders as
date-only, matching pre-Round-13 behaviour.
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_tasks_deadline_time"
down_revision = "0012_src_docs_received_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("deadline_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "deadline_time")
