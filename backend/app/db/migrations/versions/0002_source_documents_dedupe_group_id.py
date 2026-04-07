"""source_documents dedupe_group_id for task updates across syncs

Revision ID: 0002_dedupe_group
Revises: 0001_init_schema
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_dedupe_group"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("dedupe_group_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_source_documents_dedupe_group_id",
        "source_documents",
        ["dedupe_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_documents_dedupe_group_id", table_name="source_documents")
    op.drop_column("source_documents", "dedupe_group_id")
