"""enforce idempotent source_documents via unique (user_id, source_type, source_ref)

Revision ID: 0006_source_documents_unique_source_ref
Revises: 0005_tasks_deadline_v2
Create Date: 2026-04-18

Background (pass 5 forensic):

Production Redis + Postgres cross-check showed 342 gmail source_documents
with only 13 unique content_hashes — same Gmail message re-ingested up
to 91 times for the same user. Each re-ingest triggered a fresh pipeline
run (2–3 LLM calls), which is the dominant amplifier behind the chronic
429 Groq rate-limit pressure observed in LangSmith. The fix is
defence-in-depth: the queue consumer now looks up an existing row
before inserting, and this migration adds a database-level unique
constraint so even a race between two workers cannot double-ingest.

Before adding the constraint we collapse any existing duplicate rows to
the first occurrence per ``(user_id, source_type, source_ref)`` so the
``CREATE UNIQUE INDEX`` step does not fail. Child rows in
``pipeline_runs`` and ``tasks`` that pointed at the deleted duplicates
are re-pointed at the surviving row; the ``dedupe_group_id`` and
``content_hash`` of the kept row are left untouched.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_sourcedocs_uniq_ref"
down_revision = "0005_tasks_deadline_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id, source_type, source_ref
                       ORDER BY created_at, id
                   ) AS rn,
                   FIRST_VALUE(id) OVER (
                       PARTITION BY user_id, source_type, source_ref
                       ORDER BY created_at, id
                   ) AS keep_id
            FROM source_documents
        ),
        dups AS (
            SELECT id AS dup_id, keep_id
            FROM ranked
            WHERE rn > 1
        )
        UPDATE pipeline_runs pr
        SET source_doc_id = d.keep_id
        FROM dups d
        WHERE pr.source_doc_id = d.dup_id;
    """))
    conn.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id, source_type, source_ref
                       ORDER BY created_at, id
                   ) AS rn,
                   FIRST_VALUE(id) OVER (
                       PARTITION BY user_id, source_type, source_ref
                       ORDER BY created_at, id
                   ) AS keep_id
            FROM source_documents
        ),
        dups AS (
            SELECT id AS dup_id, keep_id
            FROM ranked
            WHERE rn > 1
        )
        UPDATE tasks t
        SET source_doc_id = d.keep_id
        FROM dups d
        WHERE t.source_doc_id = d.dup_id;
    """))
    conn.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id, source_type, source_ref
                       ORDER BY created_at, id
                   ) AS rn
            FROM source_documents
        )
        DELETE FROM source_documents
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
    """))
    op.create_index(
        "uq_source_documents_user_source_ref",
        "source_documents",
        ["user_id", "source_type", "source_ref"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_source_documents_user_source_ref", table_name="source_documents")
