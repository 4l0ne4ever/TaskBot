"""Integration tests for ``save_tasks_service`` evidence_quote persistence.

Covers the wire added after migration 0010 (tasks.evidence_quote, Phase 7.1).
Two paths must both persist the quote:
  - create: a brand-new task stores the extraction's evidence_quote;
  - update-in-place (dedupe reuse): a re-extracted task REFRESHES the quote
    rather than keeping the stale prior value (the explicit Decision 3
    requirement — a newer message in the same thread may carry a better quote).

Skipped automatically when local Postgres is unreachable. Requires migration
0010 applied to the local DB.
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


async def _seed_user_and_doc(dedupe_group_id: str | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(id=uuid.uuid4(), email=f"x-eq-save-{uuid.uuid4()}@example.invalid")
            s.add(user)
            await s.flush()
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="gmail",
                source_ref=f"eq-{uuid.uuid4()}",
                dedupe_group_id=dedupe_group_id,
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(eq seed)",
            )
            s.add(doc)
            await s.flush()
            return user.id, doc.id


async def _add_doc(user_id: uuid.UUID, dedupe_group_id: str) -> uuid.UUID:
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument

    async with AsyncSessionLocal() as s:
        async with s.begin():
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user_id,
                source_type="gmail",
                source_ref=f"eq-{uuid.uuid4()}",
                dedupe_group_id=dedupe_group_id,
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(eq seed 2)",
            )
            s.add(doc)
            await s.flush()
            return doc.id


async def _add_task(user_id: uuid.UUID, doc_id: uuid.UUID, *, title: str, evidence_quote: str | None) -> uuid.UUID:
    from app.db.session import AsyncSessionLocal
    from app.models import Task

    async with AsyncSessionLocal() as s:
        async with s.begin():
            t = Task(
                id=uuid.uuid4(),
                user_id=user_id,
                source_doc_id=doc_id,
                title=title,
                status="pending",
                evidence_quote=evidence_quote,
            )
            s.add(t)
            await s.flush()
            return t.id


async def _read_task_quotes(user_id: uuid.UUID) -> list[tuple[str, str | None]]:
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models import Task

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(Task).where(Task.user_id == user_id))).scalars().all()
        return [(r.title, r.evidence_quote) for r in rows]


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


def _state(user_id: uuid.UUID, source_doc_id: uuid.UUID, *, title: str, evidence_quote: str, dedupe_group_id: str | None = None) -> dict:
    meta: dict = {"sent_at": "2026-05-20"}
    if dedupe_group_id:
        meta["dedupe_group_id"] = dedupe_group_id
    return {
        "user_id": str(user_id),
        "source_doc_id": str(source_doc_id),
        "validated_tasks": [
            {
                "title": title,
                "assignee": "Lê Minh Đức",
                "deadline": "2026-04-12",
                "decision_band": "accept",
                "abstained": False,
                "missing_fields": [],
                "source_ref": "email-2",
                "evidence_quote": evidence_quote,
            }
        ],
        "conflicts": [],
        "errors": [],
        "metadata": meta,
    }


@_db_required
def test_save_persists_evidence_quote_on_create():
    from app.services.save_tasks_service import save_tasks_sync

    user_id, doc_id = asyncio.run(_seed_user_and_doc())
    try:
        state = _state(user_id, doc_id, title="Submit Q1 report", evidence_quote="nộp trước thứ Sáu")
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_task_quotes(user_id))
        assert len(rows) == 1
        assert rows[0] == ("Submit Q1 report", "nộp trước thứ Sáu")
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_reuse_path_refreshes_evidence_quote():
    """Decision 3: a re-extraction in the same dedupe group must overwrite the
    surviving task's evidence_quote with the new value, not keep the stale one."""
    from app.services.save_tasks_service import save_tasks_sync

    group = f"thread-{uuid.uuid4()}"
    user_id, doc_old = asyncio.run(_seed_user_and_doc(dedupe_group_id=group))
    try:
        # Existing task in the group carries the OLD quote.
        asyncio.run(_add_task(user_id, doc_old, title="Submit Q1 report", evidence_quote="OLD quote"))
        # A new message in the same thread re-extracts the same task with a NEW quote.
        doc_new = asyncio.run(_add_doc(user_id, group))
        state = _state(
            user_id, doc_new, title="Submit Q1 report", evidence_quote="NEW better quote", dedupe_group_id=group
        )
        out = save_tasks_sync(state)
        assert out.get("errors") == [], f"unexpected save errors: {out.get('errors')}"
        rows = asyncio.run(_read_task_quotes(user_id))
        # Reuse path updates in place — still exactly one task, with the NEW quote.
        assert len(rows) == 1, f"expected reuse (1 task), got {len(rows)}: {rows}"
        assert rows[0] == ("Submit Q1 report", "NEW better quote")
    finally:
        asyncio.run(_cleanup(user_id))
