"""Cross-source candidate loader for multi-source conflict detection.

Phase 2.2 wants ``validate_tasks`` to ask: *"for each new task this run
produces, is there an existing task from a different platform — Gmail
thread, Drive file, upload — that refers to the same deliverable?"*. This
loader provides the candidate set.

Query shape:
  - tasks for the same ``user_id``
  - excluding the current ``source_doc_id`` (intra-doc / intra-batch are
    handled separately by ``_detect_intra_batch_conflicts``)
  - ``status != 'done'`` (actionable only — completed work isn't a conflict)
  - ``created_at`` within the last ``lookback_days`` (focus on what's still
    relevant; older items would just be noise)
  - includes the joined ``source_type`` so the detector can enforce the
    cross-platform rule (Gmail vs Drive vs upload)
  - includes the person-entity canonical set for entity-overlap matching

The function returns a list of dicts; downstream pure-function detector
operates on dicts so it can be unit-tested without a DB.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.entity import Entity
from app.models.relationship import Relationship
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


async def async_load_cross_source_candidates(
    state: PipelineState,
    *,
    lookback_days: int,
) -> list[dict]:
    """Return existing-task candidates with their person-entity sets.

    Each dict shape::

        {
          "id": "<task_uuid>",
          "title": "<task title>",
          "assignee": "<raw assignee or None>",
          "assignee_canonical": "<canonical or None>",
          "deadline": "<iso date or None>",
          "source_doc_id": "<source_doc_uuid>",
          "source_type": "gmail" | "drive" | "upload",
          "entity_canonicals": {"Hương", "Minh", …},  # person entities only
        }
    """
    user_uuid = _parse_uuid(state.get("user_id") if isinstance(state.get("user_id"), str) else None)
    cur_doc_uuid = _parse_uuid(
        state.get("source_doc_id") if isinstance(state.get("source_doc_id"), str) else None
    )
    if not user_uuid:
        return []

    lookback = max(int(lookback_days), 0)
    cutoff = datetime.now(UTC) - timedelta(days=lookback)

    async with AsyncSessionLocal() as session:
        # ── Pull candidate tasks (user-scoped, not the current doc, fresh, not done)
        stmt = (
            select(
                Task.id,
                Task.title,
                Task.assignee,
                Task.assignee_canonical,
                Task.deadline,
                Task.source_doc_id,
                SourceDocument.source_type,
            )
            .join(SourceDocument, Task.source_doc_id == SourceDocument.id)
            .where(
                Task.user_id == user_uuid,
                Task.status != "done",
                Task.created_at >= cutoff,
            )
        )
        if cur_doc_uuid is not None:
            stmt = stmt.where(Task.source_doc_id != cur_doc_uuid)
        rows = (await session.execute(stmt)).all()
        if not rows:
            return []

        candidate_ids = [r.id for r in rows]

        # ── Pull the person-entity set for each candidate task in one query
        ent_stmt = (
            select(Relationship.to_task_id, Entity.canonical_name)
            .join(Entity, Relationship.from_entity_id == Entity.id)
            .where(
                Relationship.user_id == user_uuid,
                Relationship.to_task_id.in_(candidate_ids),
                Entity.entity_type == "person",
            )
        )
        ent_rows = (await session.execute(ent_stmt)).all()

    entity_by_task: dict[uuid.UUID, set[str]] = {}
    for tid, canonical in ent_rows:
        if not isinstance(canonical, str) or not canonical.strip():
            continue
        entity_by_task.setdefault(tid, set()).add(canonical.strip())

    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "title": r.title or "",
                "assignee": r.assignee,
                "assignee_canonical": r.assignee_canonical,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "source_doc_id": str(r.source_doc_id) if r.source_doc_id else None,
                "source_type": r.source_type,
                "entity_canonicals": entity_by_task.get(r.id, set()),
            }
        )
    return out


def _run_async(state: PipelineState, *, lookback_days: int) -> list[dict]:
    return asyncio.run(async_load_cross_source_candidates(state, lookback_days=lookback_days))


def load_cross_source_candidates_sync(
    state: PipelineState,
    *,
    lookback_days: int,
) -> list[dict]:
    """Sync wrapper mirroring ``existing_tasks_loader`` so callers can use this
    from a synchronous pipeline node."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_async(state, lookback_days=lookback_days)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_async, state, lookback_days=lookback_days).result()
