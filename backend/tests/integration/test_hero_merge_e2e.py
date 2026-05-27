"""End-to-end test for hero scenario 2: thread-update merge + calendar resync.

The merge endpoint is unit-tested in ``test_tasks_api.py`` against a *mocked*
session — that proves the control flow but not that the row mutations actually
commit. This test runs the real ``merge_conflict`` handler against real Postgres
so we know the survivor's deadline is genuinely overwritten, the source task is
genuinely dismissed, the conflict is genuinely resolved, and a calendar_resync
job is genuinely enqueued.

Skipped automatically when the local Postgres is unreachable (mirrors
``test_conflicts_priority_sort.py``). The Redis enqueue and the Google-token
dance are stubbed — those have their own coverage (queue_consumer tests and the
mocked-session merge tests); here we care about the database truth.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest


def _probe_db() -> bool:
    import os
    import socket

    try:
        from app.config import get_settings

        url = os.environ.get("DATABASE_URL") or get_settings().database_url
        rest = url.split("@", 1)[-1].split("/", 1)[0]
        host, _, port = rest.partition(":")
        s = socket.socket()
        s.settimeout(1)
        ok = s.connect_ex((host, int(port or 5432))) == 0
        s.close()
        return ok
    except Exception:
        return False


_db_required = pytest.mark.skipif(not _probe_db(), reason="local Postgres not reachable")


async def _seed_thread_update_conflict() -> dict:
    """Insert one user + two tasks (a thread_update pair) + the conflict row.

    Survivor is the OLDER task and carries a calendar_event_id (so a resync is
    warranted). Source is NEWER and carries the corrected deadline. task_ids are
    stored survivor-first-but-it-shouldn't-matter — the handler resolves the
    survivor by created_at, and we deliberately list source first to prove the
    positional order is not what's used.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.conflict import Conflict
    from app.models.task import Task
    from app.models.user import User

    user_id = uuid.uuid4()
    survivor_id = uuid.uuid4()
    source_id = uuid.uuid4()
    conflict_id = uuid.uuid4()

    now = datetime.now(UTC)
    survivor_deadline = (now + timedelta(days=10)).date()
    source_deadline = (now + timedelta(days=17)).date()  # the corrected/new date

    async with AsyncSessionLocal() as s:
        async with s.begin():
            s.add(User(id=user_id, email=f"merge-e2e-{user_id}@example.invalid"))
            await s.flush()
            s.add(
                Task(
                    id=survivor_id,
                    user_id=user_id,
                    title="Submit Q2 compliance report",
                    assignee="Nguyễn Văn A",
                    deadline=survivor_deadline,
                    status="confirmed",
                    confirmed_by="system",
                    calendar_event_id="evt-survivor-123",
                    created_at=now - timedelta(hours=2),  # OLDER → survives
                )
            )
            s.add(
                Task(
                    id=source_id,
                    user_id=user_id,
                    title="Submit Q2 compliance report",
                    assignee="Trần Thị B",  # reassigned in the thread reply
                    deadline=source_deadline,
                    status="pending",
                    created_at=now,  # NEWER → update source, then dismissed
                )
            )
            s.add(
                Conflict(
                    id=conflict_id,
                    user_id=user_id,
                    conflict_type="deadline_conflict",
                    description="Thread reply moved the deadline and reassigned",
                    scope="thread_update",
                    task_ids=[source_id, survivor_id],  # source first on purpose
                    resolved=False,
                    created_at=now,
                )
            )
            await s.flush()

    return {
        "user_id": user_id,
        "survivor_id": survivor_id,
        "source_id": source_id,
        "conflict_id": conflict_id,
        "source_deadline": source_deadline,
        "survivor_deadline": survivor_deadline,
    }


async def _cleanup(user_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal, engine
    from app.models.conflict import Conflict
    from app.models.task import Task
    from app.models.user import User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(Conflict).where(Conflict.user_id == user_id))
            await s.execute(delete(Task).where(Task.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))
    await engine.dispose()


class _FakeRedis:
    """Captures rpush calls so the test can assert on the enqueued payload."""

    def __init__(self) -> None:
        self.pushed: list[tuple[str, str]] = []

    async def rpush(self, queue: str, payload: str) -> int:
        self.pushed.append((queue, payload))
        return len(self.pushed)


@_db_required
def test_thread_update_merge_persists_and_enqueues_resync(monkeypatch):
    """Merge ``deadline`` from the newer reply into the older surviving task,
    verify the change committed to Postgres, and verify a calendar_resync job
    was enqueued for the survivor."""
    import json

    from app.schemas.conflict import CalendarSyncInfo, ConflictMerge

    async def _run():
        seeded = await _seed_thread_update_conflict()
        fake_redis = _FakeRedis()

        # Stub the token dance (no real Google) and the Redis client (capture).
        async def _fake_payload(_user):
            return "plaintext-access-token", CalendarSyncInfo(
                status="queued", reason=None, message="Calendar update queued."
            )

        async def _fake_get_redis():
            return fake_redis

        monkeypatch.setattr("app.api.conflicts._build_calendar_resync_payload", _fake_payload)
        monkeypatch.setattr("app.api.conflicts.get_redis", _fake_get_redis)

        try:
            from app.api.conflicts import merge_conflict
            from app.db.session import AsyncSessionLocal
            from app.models.conflict import Conflict
            from app.models.task import Task
            from app.models.user import User

            async with AsyncSessionLocal() as db:
                user = User(id=seeded["user_id"], email="x")  # only .id is read
                resp = await merge_conflict(
                    conflict_id=seeded["conflict_id"],
                    body=ConflictMerge(fields=["deadline"]),
                    db=db,
                    current_user=user,
                )

            # ── response: older task survives, newer is dismissed ──
            assert resp.merged_task_id == seeded["survivor_id"]
            assert resp.dismissed_task_id == seeded["source_id"]
            assert resp.calendar_sync.status == "queued"

            # ── DB truth: re-read in a fresh session (proves it committed) ──
            async with AsyncSessionLocal() as db2:
                survivor = await db2.get(Task, seeded["survivor_id"])
                source = await db2.get(Task, seeded["source_id"])
                conflict = await db2.get(Conflict, seeded["conflict_id"])

                # survivor took the reply's deadline, kept its identity + event
                assert survivor.deadline == seeded["source_deadline"]
                assert survivor.calendar_event_id == "evt-survivor-123"
                assert survivor.status == "confirmed"  # identity/status preserved
                # prior state snapshotted for revert/audit
                assert survivor.previous_revision is not None
                assert survivor.previous_revision["deadline"] == seeded["survivor_deadline"].isoformat()

                # source dismissed; conflict resolved
                assert source.status == "dismissed"
                assert conflict.resolved is True
                assert conflict.description.startswith("[merged:thread_update]")

            # ── resync enqueued for the survivor ──
            assert len(fake_redis.pushed) == 1
            _queue, payload = fake_redis.pushed[0]
            job = json.loads(payload)
            assert job["source_type"] == "calendar_resync"
            assert job["task_id"] == str(seeded["survivor_id"])
            assert job["triggered_by"] == "conflict_merge"
            assert job["access_token"] == "plaintext-access-token"
        finally:
            await _cleanup(seeded["user_id"])

    asyncio.run(_run())


@_db_required
def test_merge_without_calendar_change_does_not_enqueue(monkeypatch):
    """Merging only ``assignee`` (a non-calendar field) must NOT enqueue a
    resync even though the survivor has a calendar event — nothing the calendar
    reflects changed. Proves the enqueue is conditional, not reflexive."""
    from app.schemas.conflict import ConflictMerge

    async def _run():
        seeded = await _seed_thread_update_conflict()
        fake_redis = _FakeRedis()

        async def _fake_get_redis():
            return fake_redis

        monkeypatch.setattr("app.api.conflicts.get_redis", _fake_get_redis)

        try:
            from app.api.conflicts import merge_conflict
            from app.db.session import AsyncSessionLocal
            from app.models.task import Task
            from app.models.user import User

            async with AsyncSessionLocal() as db:
                user = User(id=seeded["user_id"], email="x")
                resp = await merge_conflict(
                    conflict_id=seeded["conflict_id"],
                    body=ConflictMerge(fields=["assignee"]),
                    db=db,
                    current_user=user,
                )

            assert resp.calendar_sync.status == "skipped"
            assert resp.calendar_sync.reason == "no_calendar_change"
            assert fake_redis.pushed == []

            async with AsyncSessionLocal() as db2:
                survivor = await db2.get(Task, seeded["survivor_id"])
                # assignee took the reply's value; deadline untouched
                assert survivor.assignee == "Trần Thị B"
                assert survivor.deadline == seeded["survivor_deadline"]
        finally:
            await _cleanup(seeded["user_id"])

    asyncio.run(_run())
