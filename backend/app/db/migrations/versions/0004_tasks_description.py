"""add description column to tasks

Revision ID: 0004_tasks_description
Revises: 0003_prev_revision
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_tasks_description"
down_revision = "0003_prev_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "description")
