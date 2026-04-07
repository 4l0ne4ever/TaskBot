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

        if group_id:
            stmt = (
                select(Task)
                .join(SourceDocument, Task.source_doc_id == SourceDocument.id)
                .where(
                    Task.user_id == user_uuid,
                    SourceDocument.dedupe_group_id == group_id,
                )
            )
            rows = list((await session.execute(stmt)).scalars().all())
        else:
            stmt = (
                select(Task)
                .where(Task.user_id == user_uuid)
                .order_by(Task.updated_at.desc())
                .limit(100)
            )
            rows = list((await session.execute(stmt)).scalars().all())

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
