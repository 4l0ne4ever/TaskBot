"""Add source_documents.received_at column.

Revision ID: 0012_src_docs_received_at
Revises: 0011_tasks_confirmed_by
Create Date: 2026-05-30

Background:

Until now the task-detail "Source" panel showed ``source_documents.created_at``
— i.e. the moment TaskBot **synced** the email, not the moment Google
**received** it. For most dogfood emails the two are days apart, and the
display read as the wrong date (`5/29/2026` for an email that arrived earlier
in May). Gmail's parsed ``sent_at_iso`` is already computed by
``queue_consumer._parse_gmail_message`` (from ``Date:`` header or
``internalDate`` fallback) and threaded into pipeline state — it just was
never persisted onto the row.

This migration adds the column. The insert path in
``queue_consumer._process_gmail_job`` is updated in the same commit to set
``received_at = parsed["sent_at"]`` when present. Drive sync currently leaves
this NULL — file ``modifiedTime`` is a defensible analog for a future commit
but is not in scope here. The frontend renders ``received_at`` when set and
falls back to ``created_at`` so existing rows continue to display.

No backfill: cheap-to-compute but requires re-parsing each archived email's
headers, and the existing rows already display "something date-looking" so a
backfill would be cosmetic. New syncs populate the column going forward.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_src_docs_received_at"
down_revision = "0011_tasks_confirmed_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_documents", "received_at")
