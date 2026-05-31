"""Thin wrappers that bridge the sync LangGraph pipeline to async callers,
plus dedup helpers that gate "have we already processed this source?" before
spending an LLM call.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.pipeline.graph import pipeline
from app.pipeline.llm import collect_provenance

from ._runtime import logger


async def find_existing_source_doc(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_ref: str,
) -> SourceDocument | None:
    """Return an existing ``source_documents`` row for this logical source.

    The ``(user_id, source_type, source_ref)`` triple is unique (migration
    ``0006_source_documents_unique_source_ref``). Callers use this as the
    first step of an idempotency check — if the row exists and
    ``processed_at`` is already set, the caller should skip the whole
    pipeline invocation. Production cross-check (pass 5) showed a single
    Gmail message being ingested 91 times for one user without this guard;
    that was the dominant driver of chronic 429s.
    """
    if not source_ref:
        return None
    stmt = select(SourceDocument).where(
        SourceDocument.user_id == user_id,
        SourceDocument.source_type == source_type,
        SourceDocument.source_ref == source_ref,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _run_pipeline_in_thread(state: dict) -> dict:
    """Run the synchronous LangGraph pipeline in its own event loop / thread.

    Each invocation opens a fresh :func:`collect_provenance` scope so per-call
    LLM routing (primary vs fallback) can be attributed back to this pipeline
    run. The scope's data is persisted by ``record_pipeline_run_trace`` via
    the validate node; here we just make sure every job gets its own isolated
    scope even under concurrent thread dispatch.
    """
    with collect_provenance():
        return pipeline.invoke(state)


async def invoke_pipeline(state: dict) -> dict:
    return await asyncio.to_thread(_run_pipeline_in_thread, state)


async def mark_run_failed(run_id: str, error_msg: str = "pipeline exception") -> None:
    """Mark a PipelineRun as failed using a fresh session — safe to call
    after pipeline errors."""
    if not run_id:
        return
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = (
                    update(PipelineRun)
                    .where(PipelineRun.id == uuid.UUID(run_id))
                    .values(
                        status="failed",
                        error_message=error_msg,
                        completed_at=datetime.now(UTC),
                    )
                )
                await session.execute(stmt)
    except Exception:
        logger.exception("failed to mark pipeline run %s as failed", run_id)


_TIME_RANGE_MAP: dict[str, timedelta] = {
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def time_range_to_datetime(time_range: str) -> datetime:
    delta = _TIME_RANGE_MAP.get(time_range, timedelta(days=1))
    return datetime.now(UTC) - delta


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
