"""End-to-end test that ``GET /tasks/conflicts?sort=priority`` actually
returns rows in the documented hierarchy when the data hits real Postgres.

The mock-based test in ``test_tasks_api.py`` only verifies the compiled SQL
includes a CASE expression; this one verifies the CASE *values* are right
so a swapped priority slot can't slip past review.

Skipped automatically when the local Postgres is unreachable.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest


def _probe_db() -> bool:
    # We use socket.connect_ex rather than opening a SQLAlchemy session — the
    # asyncpg pool would otherwise bind a connection to *this* event loop,
    # leave it cached, and reject the test's own asyncio.run() with
    # "another operation is in progress" because the cached connection is
    # bound to a dead loop. A simple TCP probe avoids the pool entirely.
    import socket

    try:
        import os

        from app.config import get_settings

        url = os.environ.get("DATABASE_URL") or get_settings().database_url
        # Cheap parse: extract host:port; this is the only thing we need.
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


async def _seed_user_with_conflicts() -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Insert one user and one Conflict per scope value, plus one with NULL
    scope (legacy). Returns the user id and the conflict ids keyed by scope
    so the test can assert on the returned order.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.conflict import Conflict
    from app.models.user import User

    user_id = uuid.uuid4()
    # Insert intentionally OUT OF priority order — if the sort were a no-op,
    # the test would see this same order and pass falsely. The expected order
    # under sort=priority is multi_source -> thread_update -> inter_doc ->
    # intra_batch -> NULL, regardless of insert order or created_at.
    rows = [
        ("inter_doc", uuid.uuid4()),
        ("intra_batch", uuid.uuid4()),
        ("multi_source", uuid.uuid4()),
        (None, uuid.uuid4()),  # legacy row, no scope
        ("thread_update", uuid.uuid4()),
    ]
    async with AsyncSessionLocal() as s:
        async with s.begin():
            s.add(User(id=user_id, email=f"x-prio-{user_id}@example.invalid"))
            await s.flush()
            for scope, cid in rows:
                s.add(
                    Conflict(
                        id=cid,
                        user_id=user_id,
                        conflict_type="deadline_conflict",
                        description=f"test {scope}",
                        scope=scope,
                        resolved=False,
                        created_at=datetime.now(UTC),
                    )
                )
            await s.flush()
    return user_id, rows


async def _cleanup(user_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal, engine
    from app.models.conflict import Conflict
    from app.models.user import User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(Conflict).where(Conflict.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))
    # Backend's session uses a pooled engine (production default); the pool
    # would otherwise cache the asyncpg connection from THIS event loop and
    # the next test's asyncio.run would inherit a connection bound to a dead
    # loop ("got Future attached to a different loop"). dispose() empties the
    # pool so each test starts with a fresh asyncpg connection.
    await engine.dispose()


@_db_required
def test_priority_sort_returns_rows_in_canonical_hierarchy_order():
    """multi_source first, intra_batch last, NULL last-last. Bypasses the
    HTTP layer and calls the route handler directly with a real session to
    keep the test focused on the SQL ordering — TestClient with auth deps
    would just add noise."""
    from app.api.conflicts import list_conflicts
    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async def _run():
        user_id, rows = await _seed_user_with_conflicts()
        try:
            async with AsyncSessionLocal() as db:
                user = User(id=user_id, email="x")  # only .id is read
                result = await list_conflicts(
                    resolved=None,
                    scope=None,
                    sort="priority",
                    limit=50,
                    offset=0,
                    db=db,
                    current_user=user,
                )
            scopes_in_order = [c.scope for c in result]
            assert scopes_in_order == [
                "multi_source",
                "thread_update",
                "inter_doc",
                "intra_batch",
                None,
            ], f"hierarchy violated: {scopes_in_order}"
        finally:
            await _cleanup(user_id)

    asyncio.run(_run())


@_db_required
def test_scope_filter_returns_only_matching_rows():
    """``?scope=thread_update`` returns only the matching row even when
    other scopes are present for the same user."""
    from app.api.conflicts import list_conflicts
    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async def _run():
        user_id, _rows = await _seed_user_with_conflicts()
        try:
            async with AsyncSessionLocal() as db:
                user = User(id=user_id, email="x")
                result = await list_conflicts(
                    resolved=None,
                    scope="thread_update",
                    sort="created_at",
                    limit=50,
                    offset=0,
                    db=db,
                    current_user=user,
                )
            assert len(result) == 1
            assert result[0].scope == "thread_update"
        finally:
            await _cleanup(user_id)

    asyncio.run(_run())
