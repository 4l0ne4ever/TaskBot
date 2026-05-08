"""add deadline_v2 and uncertainty to tasks

Revision ID: 0005_tasks_deadline_v2
Revises: 0004_tasks_description
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_tasks_deadline_v2"
down_revision = "0004_tasks_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("deadline_v2", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tasks", sa.Column("uncertainty", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "uncertainty")
    op.drop_column("tasks", "deadline_v2")
