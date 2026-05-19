"""Integration tests for ``cross_source_candidates_loader``.

These hit the real Postgres dev DB to verify the SQL filters work as
specified (status != 'done', lookback window, source_doc exclusion, entity
join). Skipped automatically when the DB is unreachable so CI without a DB
still runs the rest of the suite.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta

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


async def _make_user_with_two_docs() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert one user with a Gmail doc and a Drive doc. Returns (user, gmail, drive)."""
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(id=uuid.uuid4(), email=f"x-loader-{uuid.uuid4()}@example.invalid")
            s.add(user)
            await s.flush()
            doc_gmail = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="gmail",
                source_ref=f"g-{uuid.uuid4()}",
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            )
            doc_drive = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="drive",
                source_ref=f"d-{uuid.uuid4()}",
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            )
            s.add(doc_gmail)
            s.add(doc_drive)
            await s.flush()
            return user.id, doc_gmail.id, doc_drive.id


async def _make_task(
    user_id: uuid.UUID,
    source_doc_id: uuid.UUID,
    *,
    title: str,
    assignee_canonical: str | None,
    status: str = "pending",
    created_offset_days: int = 0,
) -> uuid.UUID:
    """Insert a task with controllable created_at via a follow-up UPDATE."""
    from sqlalchemy import update

    from app.db.session import AsyncSessionLocal
    from app.models import Task

    async with AsyncSessionLocal() as s:
        async with s.begin():
            task = Task(
                id=uuid.uuid4(),
                user_id=user_id,
                source_doc_id=source_doc_id,
                title=title,
                assignee_canonical=assignee_canonical,
                status=status,
            )
            s.add(task)
            await s.flush()
            tid = task.id
            if created_offset_days:
                shifted = datetime.now(UTC) - timedelta(days=created_offset_days)
                await s.execute(
                    update(Task).where(Task.id == tid).values(created_at=shifted)
                )
            return tid


async def _add_person_entity_with_assigned_edge(
    user_id: uuid.UUID, task_id: uuid.UUID, canonical: str
) -> uuid.UUID:
    """Create a person entity and an assigned_to relationship to the task."""
    from app.db.session import AsyncSessionLocal
    from app.models import Entity, Relationship

    async with AsyncSessionLocal() as s:
        async with s.begin():
            ent = Entity(
                id=uuid.uuid4(),
                user_id=user_id,
                entity_type="person",
                canonical_name=canonical,
                aliases=[],
            )
            s.add(ent)
            await s.flush()
            rel = Relationship(
                id=uuid.uuid4(),
                user_id=user_id,
                from_entity_id=ent.id,
                to_task_id=task_id,
                relationship_type="assigned_to",
            )
            s.add(rel)
            await s.flush()
            return ent.id


async def _cleanup(user_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models import Entity, Relationship, SourceDocument, Task, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(Relationship).where(Relationship.user_id == user_id))
            await s.execute(delete(Entity).where(Entity.user_id == user_id))
            await s.execute(delete(Task).where(Task.user_id == user_id))
            await s.execute(delete(SourceDocument).where(SourceDocument.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))


@_db_required
def test_loader_returns_other_source_doc_tasks_with_entities():
    """Happy path: a Drive task (with assigned_to person entity) is returned
    when the loader is invoked for a state pointing at a *Gmail* doc."""
    from app.services.cross_source_candidates_loader import (
        load_cross_source_candidates_sync,
    )

    async def _setup():
        user_id, doc_gmail, doc_drive = await _make_user_with_two_docs()
        drive_task = await _make_task(
            user_id,
            doc_drive,
            title="Submit Q1 report",
            assignee_canonical="Hương",
        )
        await _add_person_entity_with_assigned_edge(user_id, drive_task, "Hương")
        return user_id, doc_gmail, drive_task

    user_id, doc_gmail, drive_task = asyncio.run(_setup())
    try:
        state = {
            "user_id": str(user_id),
            "source_doc_id": str(doc_gmail),  # new run is a Gmail doc
        }
        out = load_cross_source_candidates_sync(state, lookback_days=30)
        assert len(out) == 1
        cand = out[0]
        assert cand["id"] == str(drive_task)
        assert cand["title"] == "Submit Q1 report"
        assert cand["source_type"] == "drive"
        assert "Hương" in cand["entity_canonicals"]
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_loader_excludes_done_tasks():
    from app.services.cross_source_candidates_loader import (
        load_cross_source_candidates_sync,
    )

    async def _setup():
        user_id, doc_gmail, doc_drive = await _make_user_with_two_docs()
        await _make_task(user_id, doc_drive, title="Done task", assignee_canonical=None, status="done")
        return user_id, doc_gmail

    user_id, doc_gmail = asyncio.run(_setup())
    try:
        state = {"user_id": str(user_id), "source_doc_id": str(doc_gmail)}
        out = load_cross_source_candidates_sync(state, lookback_days=30)
        assert out == []
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_loader_excludes_tasks_outside_lookback_window():
    from app.services.cross_source_candidates_loader import (
        load_cross_source_candidates_sync,
    )

    async def _setup():
        user_id, doc_gmail, doc_drive = await _make_user_with_two_docs()
        # 45 days old → outside a 30-day lookback
        await _make_task(
            user_id,
            doc_drive,
            title="Old task",
            assignee_canonical=None,
            created_offset_days=45,
        )
        return user_id, doc_gmail

    user_id, doc_gmail = asyncio.run(_setup())
    try:
        state = {"user_id": str(user_id), "source_doc_id": str(doc_gmail)}
        out = load_cross_source_candidates_sync(state, lookback_days=30)
        assert out == []
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_loader_excludes_current_source_doc_id():
    """A task in the same source_doc as the current run is not a candidate."""
    from app.services.cross_source_candidates_loader import (
        load_cross_source_candidates_sync,
    )

    async def _setup():
        user_id, doc_gmail, _doc_drive = await _make_user_with_two_docs()
        await _make_task(user_id, doc_gmail, title="Same-doc task", assignee_canonical=None)
        return user_id, doc_gmail

    user_id, doc_gmail = asyncio.run(_setup())
    try:
        state = {"user_id": str(user_id), "source_doc_id": str(doc_gmail)}
        out = load_cross_source_candidates_sync(state, lookback_days=30)
        assert out == []
    finally:
        asyncio.run(_cleanup(user_id))


@_db_required
def test_loader_perf_baseline_under_200ms_for_small_dataset():
    """Implementation-note B: loose perf sanity check on a small dataset.
    The query joins tasks → source_documents → relationships → entities; on
    a dev DB with a handful of rows it should be well under 200ms. This
    test fails loudly if a future change accidentally turns the query into
    a sequential scan.
    """
    from app.services.cross_source_candidates_loader import (
        load_cross_source_candidates_sync,
    )

    async def _setup():
        user_id, doc_gmail, doc_drive = await _make_user_with_two_docs()
        # 5 candidates is plenty to exercise the join path.
        for i in range(5):
            tid = await _make_task(
                user_id, doc_drive, title=f"Task {i}", assignee_canonical=f"Person{i}"
            )
            await _add_person_entity_with_assigned_edge(user_id, tid, f"Person{i}")
        return user_id, doc_gmail

    user_id, doc_gmail = asyncio.run(_setup())
    try:
        state = {"user_id": str(user_id), "source_doc_id": str(doc_gmail)}
        # Warm the connection pool first so the first ``asyncio.run`` cost
        # isn't measured as the query.
        load_cross_source_candidates_sync(state, lookback_days=30)
        t0 = time.perf_counter()
        out = load_cross_source_candidates_sync(state, lookback_days=30)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert len(out) == 5
        assert elapsed_ms < 200, f"loader took {elapsed_ms:.1f}ms — investigate (was the index lost?)"
    finally:
        asyncio.run(_cleanup(user_id))
