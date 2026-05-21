"""Unit tests for Phase 7.3 supersede-reset behaviour in save_tasks_service.

When the pipeline re-extracts a task that is already status="confirmed" via the
update-in-place (dedupe reuse) path, the confirmed status must be reset to
"pending" so the user sees it again and can re-confirm. Without this gate,
field changes (deadline, assignee) would be silently applied to a confirmed
task and flow into the calendar without user awareness.
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


async def _seed(*, group: str, confirmed: bool) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed user + first doc + task. Returns (user_id, doc_id, task_id)."""
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument, Task, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(id=uuid.uuid4(), email=f"sr-{uuid.uuid4()}@example.invalid")
            s.add(user)
            await s.flush()
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="gmail",
                source_ref=f"sr-{uuid.uuid4()}",
                dedupe_group_id=group,
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(seed)",
            )
            s.add(doc)
            await s.flush()
            task = Task(
                id=uuid.uuid4(),
                user_id=user.id,
                source_doc_id=doc.id,
                title="Ship Q2 report",
                status="confirmed" if confirmed else "pending",
            )
            s.add(task)
            await s.flush()
            return user.id, doc.id, task.id


async def _add_doc(user_id: uuid.UUID, group: str) -> uuid.UUID:
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument

    async with AsyncSessionLocal() as s:
        async with s.begin():
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user_id,
                source_type="gmail",
                source_ref=f"sr-{uuid.uuid4()}",
                dedupe_group_id=group,
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(update)",
            )
            s.add(doc)
            await s.flush()
            return doc.id


async def _read_status(task_id: uuid.UUID) -> str | None:
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models import Task

    async with AsyncSessionLocal() as s:
        t = (await s.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
        return t.status if t else None


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


def _state(user_id: uuid.UUID, doc_id: uuid.UUID, *, group: str) -> dict:
    return {
        "user_id": str(user_id),
        "source_doc_id": str(doc_id),
        "validated_tasks": [
            {
                "title": "Ship Q2 report",
                "assignee": "Trần Văn B",
                "deadline": "2026-06-30",
                "decision_band": "accept",
                "abstained": False,
                "missing_fields": [],
                "source_ref": "email-update",
            }
        ],
        "conflicts": [],
        "errors": [],
        "metadata": {"sent_at": "2026-05-21", "dedupe_group_id": group},
    }


@_db_required
def test_supersede_resets_confirmed_to_pending():
    """A confirmed task that is superseded by the pipeline must be reset to pending."""
    from app.services.save_tasks_service import save_tasks_sync

    group = f"thread-{uuid.uuid4()}"
    user_id, _doc_old, task_id = asyncio.run(_seed(group=group, confirmed=True))
    try:
        assert asyncio.run(_read_status(task_id)) == "confirmed"

        doc_new = asyncio.run(_add_doc(user_id, group))
        out = save_tasks_sync(_state(user_id, doc_new, group=group))
        assert out.get("errors") == [], out.get("errors")
        assert asyncio.run(_read_status(task_id)) == "pending"
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_supersede_leaves_pending_as_pending():
    """A pending task superseded by the pipeline remains pending (no spurious change)."""
    from app.services.save_tasks_service import save_tasks_sync

    group = f"thread-{uuid.uuid4()}"
    user_id, _doc_old, task_id = asyncio.run(_seed(group=group, confirmed=False))
    try:
        assert asyncio.run(_read_status(task_id)) == "pending"

        doc_new = asyncio.run(_add_doc(user_id, group))
        out = save_tasks_sync(_state(user_id, doc_new, group=group))
        assert out.get("errors") == [], out.get("errors")
        assert asyncio.run(_read_status(task_id)) == "pending"
    finally:
        asyncio.run(_cleanup(user_id))
