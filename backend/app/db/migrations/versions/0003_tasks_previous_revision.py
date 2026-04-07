"""Add previous_revision JSONB column to tasks for audit trail."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_prev_revision"
down_revision = "0002_dedupe_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("previous_revision", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "previous_revision")
