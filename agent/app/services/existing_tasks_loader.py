from __future__ import annotations

import asyncio
import concurrent.futures
import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.pipeline.state import PipelineState


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _task_row_to_dict(t: Task) -> dict:
    deadline_val = t.deadline.isoformat() if t.deadline else None
    tid = str(t.id)
    return {
        "id": tid,
        "title": t.title,
        "assignee": t.assignee,
        "deadline": deadline_val,
        "source_ref": tid,
    }


async def async_load_existing_tasks_for_validate(state: PipelineState) -> list[dict]:
    user_id_str = state.get("user_id")
    source_doc_id_str = state.get("source_doc_id")
    user_uuid = _parse_uuid(user_id_str if isinstance(user_id_str, str) else None)
    source_doc_uuid = _parse_uuid(source_doc_id_str if isinstance(source_doc_id_str, str) else None)
    if not user_uuid or not source_doc_uuid:
        return []

    meta = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    meta_group = meta.get("dedupe_group_id") if isinstance(meta.get("dedupe_group_id"), str) else None
    meta_group = meta_group.strip() if meta_group else None

    async with AsyncSessionLocal() as session:
        doc = await session.get(SourceDocument, source_doc_uuid)
        group_id = (doc.dedupe_group_id or "").strip() if doc else ""
        if not group_id and meta_group:
            group_id = meta_group

        # Always load recent same-user tasks across threads. Previously this
        # branch only fired when group_id was empty, which meant Gmail (every
        # message in a unique thread) NEVER saw cross-thread tasks as conflict
        # candidates — inter_doc deadline_conflict silently no-op'd for the
        # most common real-world scenario (same deliverable mentioned in two
        # separate emails). validate_tasks filters this pool by title
        # similarity (≥ conflict_title_similarity_threshold) before any LLM
        # call, so loading a wider pool only costs one extra DB query, not
        # extra LLM spend.
        recent_stmt = (
            select(Task)
            .where(
                Task.user_id == user_uuid,
                Task.source_doc_id != source_doc_uuid,
            )
            .order_by(Task.updated_at.desc())
            .limit(100)
        )
        rows: list[Task] = list((await session.execute(recent_stmt)).scalars().all())

        # When the current source_doc has a thread, also pull every same-thread
        # task even if it's outside the recent-100 window — thread_update
        # detection (Phase 2.1 + A') depends on having ALL prior thread tasks
        # visible regardless of recency, so a slow-burn thread that hasn't
        # been touched in weeks still surfaces its prior revisions.
        if group_id:
            same_thread_stmt = (
                select(Task)
                .join(SourceDocument, Task.source_doc_id == SourceDocument.id)
                .where(
                    Task.user_id == user_uuid,
                    SourceDocument.dedupe_group_id == group_id,
                    Task.source_doc_id != source_doc_uuid,
                )
            )
            same_thread_rows = list(
                (await session.execute(same_thread_stmt)).scalars().all()
            )
            seen_ids = {t.id for t in rows}
            for t in same_thread_rows:
                if t.id not in seen_ids:
                    rows.append(t)
                    seen_ids.add(t.id)

    return [_task_row_to_dict(t) for t in rows]


def _run_async(state: PipelineState) -> list[dict]:
    return asyncio.run(async_load_existing_tasks_for_validate(state))


def load_existing_tasks_for_validate_sync(state: PipelineState) -> list[dict]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_async(state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_async, state).result()
