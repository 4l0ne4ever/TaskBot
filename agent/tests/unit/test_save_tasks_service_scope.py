"""Integration tests for ``save_tasks_service`` scope persistence.

Covers the wire added after migration 0009 (conflicts.scope). Both
intra-batch and inter-doc paths must persist scope identically so the
Phase 2.3 UI sees consistent data regardless of which detector raised
the conflict. Skipped automatically when local Postgres is unreachable.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid

import pytest


def _probe_db() -> bool:
    try:
        from sqlalchemy import text as _t
        from app.db.session import AsyncSessionLocal

        async def _go() -> None:
            async with AsyncSessionLocal() as s:
                await s.execute(_t("SELECT 1"))

        asyncio.run(_go())
        return True
    except Exception:
        return False


_db_required = pytest.mark.skipif(not _probe_db(), reason="local Postgres not reachable")


async def _seed_user_and_doc() -> tuple[uuid.UUID, uuid.UUID]:
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(id=uuid.uuid4(), email=f"x-scope-save-{uuid.uuid4()}@example.invalid")
            s.add(user)
            await s.flush()
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="gmail",
                source_ref=f"smoke-scope-{uuid.uuid4()}",
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(smoke seed)",
            )
            s.add(doc)
            await s.flush()
            return user.id, doc.id


async def _read_conflict_rows(user_id: uuid.UUID) -> list[dict]:
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models import Conflict

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Conflict).where(Conflict.user_id == user_id))).scalars().all()
        return [
            {"conflict_type": r.conflict_type, "scope": r.scope, "description": r.description}
            for r in rows
        ]


async def _cleanup(user_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models import Conflict, PipelineRun, SourceDocument, Task, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(Conflict).where(Conflict.user_id == user_id))
            await s.execute(delete(Task).where(Task.user_id == user_id))
            await s.execute(delete(PipelineRun).where(PipelineRun.user_id == user_id))
            await s.execute(delete(SourceDocument).where(SourceDocument.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))


def _state_with_conflict(
    user_id: uuid.UUID, source_doc_id: uuid.UUID, *, scope: str | None, conflict_type: str
) -> dict:
    """Build a minimal validated-tasks + conflicts state for save_tasks.

    The validated task is the new emitting task; the conflict carries the
    runtime ``scope`` exactly as it would after validate_tasks tagged it.
    """
    return {
        "user_id": str(user_id),
        "source_doc_id": str(source_doc_id),
        "validated_tasks": [
            {
                "title": "Submit Q1 report",
                "assignee": "Lê Minh Đức",
                "deadline": "2026-04-12",
                "decision_band": "accept",
                "abstained": False,
                "missing_fields": [],
                "source_ref": "email-2",
            }
        ],
        "conflicts": [
            {
                "conflict_type": conflict_type,
                "description": "test conflict",
                "source_a_ref": "email-2",
                "source_b_ref": "email-1",
                "task_title": "Submit Q1 report",
                "scope": scope,
            }
        ],
        "errors": [],
        "metadata": {"sent_at": "2026-05-19"},
    }


@_db_required
def test_save_persists_scope_thread_update_from_intra_batch_path():
    """A conflict emitted by ``_detect_intra_batch_conflicts`` with
    ``scope='thread_update'`` (marker present in same source_text) must
    round-trip through save_tasks_service and land in ``conflicts.scope``."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, doc_id = asyncio.run(_seed_user_and_doc())
    try:
        state = _state_with_conflict(
            user_id, doc_id, scope="thread_update", conflict_type="assignee_conflict"
        )
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_conflict_rows(user_id))
        assert len(rows) == 1
        assert rows[0]["scope"] == "thread_update"
        assert rows[0]["conflict_type"] == "assignee_conflict"
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_save_persists_scope_inter_doc_from_inter_doc_path():
    """A conflict emitted by ``_build_conflicts_for_task`` with
    ``scope='inter_doc'`` (no marker, generic cross-document) must round-trip
    identically. Catches the consistency requirement: both detectors feed the
    same save wire, so dropping scope at the wire would silently break only
    one path and leave the other working."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, doc_id = asyncio.run(_seed_user_and_doc())
    try:
        state = _state_with_conflict(
            user_id, doc_id, scope="inter_doc", conflict_type="deadline_conflict"
        )
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_conflict_rows(user_id))
        assert len(rows) == 1
        assert rows[0]["scope"] == "inter_doc"
        assert rows[0]["conflict_type"] == "deadline_conflict"
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_save_persists_scope_multi_source():
    """Phase 2.2 multi-source path: ``scope='multi_source'`` must persist."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, doc_id = asyncio.run(_seed_user_and_doc())
    try:
        state = _state_with_conflict(
            user_id, doc_id, scope="multi_source", conflict_type="multi_source"
        )
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_conflict_rows(user_id))
        assert len(rows) == 1
        assert rows[0]["scope"] == "multi_source"
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_save_tolerates_missing_scope_legacy_shape():
    """Defensive: a conflict dict without a ``scope`` key (e.g. legacy
    in-flight records from before Phase A') must still save without error;
    the column is NULL-able and persistence must not fail."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, doc_id = asyncio.run(_seed_user_and_doc())
    try:
        state = _state_with_conflict(
            user_id, doc_id, scope=None, conflict_type="assignee_conflict"
        )
        # Strip scope entirely to mimic legacy producers.
        state["conflicts"][0].pop("scope", None)
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_conflict_rows(user_id))
        assert len(rows) == 1
        assert rows[0]["scope"] is None
    finally:
        asyncio.run(_cleanup(user_id))
