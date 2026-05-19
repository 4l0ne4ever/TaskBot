"""Tests for ``app.services.entity_extractor``.

Two test sections:

  1. **Pure-function tests** for ``find_mentioned_canonicals`` — always run.
  2. **DB-integration tests** for the upsert / refresh / orchestrator —
     skipped when the local Postgres at ``DATABASE_URL`` is unreachable
     (CI without a DB still gets the pure-function coverage).

The integration tests use unique per-user UUIDs and tear themselves down at
the end so they don't pollute the shared dev database. They also rely on the
0008_entity_graph migration being applied (verified separately in Phase 1.1).
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app.services.entity_extractor import (
    PERSON_ENTITY_TYPE,
    _gather_task_text,
    _OWNED_RELATIONSHIP_TYPES,
    find_mentioned_canonicals,
    refresh_task_relationships,
    update_entity_graph_for_tasks,
    upsert_person_entity,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1 — Pure-function tests (no DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindMentionedCanonicals:
    def test_basic_match(self):
        out = find_mentioned_canonicals("Discuss budget with Hương", ["Hương", "Minh"])
        assert out == ["Hương"]

    def test_word_boundary_prevents_substring_false_positive(self):
        # "An" appears inside "Anh" — must not match as a standalone canonical.
        out = find_mentioned_canonicals("Anh và đội báo cáo", ["An"])
        assert out == []

    def test_word_boundary_with_vietnamese_diacritics(self):
        # "Đỗ" in "Đỗ Văn Hải" — clean word boundary on whitespace.
        out = find_mentioned_canonicals("Đỗ Văn Hải and team", ["Đỗ"])
        assert out == ["Đỗ"]

    def test_diacritic_sensitive_no_fold(self):
        """Pool has 'Hương' (with diacritics); text has 'Huong' (no diacritics).
        The detector intentionally does NOT fold — silence is correct here so
        the entity graph stays consistent with assignee_resolver."""
        out = find_mentioned_canonicals("Send to Huong tomorrow", ["Hương"])
        assert out == []

    def test_exclude_assignee_from_mentions(self):
        text = "Hương sends report to Minh"
        out = find_mentioned_canonicals(text, ["Hương", "Minh"], exclude="Hương")
        assert out == ["Minh"]

    def test_exclude_is_case_insensitive(self):
        out = find_mentioned_canonicals("Hương and Minh", ["Hương", "Minh"], exclude="hương")
        assert out == ["Minh"]

    def test_dedup_when_same_canonical_appears_twice(self):
        out = find_mentioned_canonicals("Hương meet Hương later", ["Hương"])
        assert out == ["Hương"]

    def test_preserves_pool_order(self):
        out = find_mentioned_canonicals("Minh and Hương and Đỗ", ["Hương", "Đỗ", "Minh"])
        assert out == ["Hương", "Đỗ", "Minh"]

    def test_empty_text_returns_empty(self):
        assert find_mentioned_canonicals("", ["Hương"]) == []
        assert find_mentioned_canonicals(None, ["Hương"]) == []

    def test_empty_pool_returns_empty(self):
        assert find_mentioned_canonicals("Hương", []) == []

    def test_non_string_pool_entries_are_skipped(self):
        out = find_mentioned_canonicals(
            "Hương sends report", ["Hương", None, "", 123, "  "]  # type: ignore[list-item]
        )
        assert out == ["Hương"]

    def test_special_regex_chars_in_canonical_escaped(self):
        # A canonical with a regex meta-char must not break the search.
        out = find_mentioned_canonicals("Project A.B started", ["A.B"])
        assert out == ["A.B"]
        # And the dot is NOT treated as "any char" — wouldn't match "AxB".
        out2 = find_mentioned_canonicals("Project AxB started", ["A.B"])
        assert out2 == []


class TestGatherTaskText:
    def test_concatenates_title_description_evidence(self):
        t = {"title": "A", "description": "B", "evidence_quote": "C"}
        assert _gather_task_text(t) == "A B C"

    def test_none_safe(self):
        t = {"title": "Only title"}
        assert _gather_task_text(t) == "Only title"

    def test_strips_empty_parts(self):
        t = {"title": "  ", "description": "Desc"}
        assert _gather_task_text(t) == "Desc"

    def test_non_string_fields_ignored(self):
        t = {"title": "Title", "description": 123, "evidence_quote": None}  # type: ignore[dict-item]
        assert _gather_task_text(t) == "Title"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2 — DB integration tests (require local Postgres + 0008 migration)
# ═══════════════════════════════════════════════════════════════════════════════
#
# These talk to the real DB at ``DATABASE_URL``. They're guarded by a connection
# probe so CI without a DB still runs Section 1 cleanly.


_DB_AVAILABLE: bool | None = None
_DB_PROBE_ERROR: str = ""


def _probe_db_available() -> bool:
    """One-shot async probe that caches its result across the module run."""
    global _DB_AVAILABLE, _DB_PROBE_ERROR
    if _DB_AVAILABLE is not None:
        return _DB_AVAILABLE
    try:
        from sqlalchemy import text as _sql_text

        from app.db.session import AsyncSessionLocal

        async def _probe() -> None:
            async with AsyncSessionLocal() as s:
                await s.execute(_sql_text("SELECT 1"))

        asyncio.run(_probe())
        _DB_AVAILABLE = True
    except Exception as exc:  # broad on purpose: any failure → skip
        _DB_AVAILABLE = False
        _DB_PROBE_ERROR = f"{type(exc).__name__}: {exc}"
    return _DB_AVAILABLE


_db_required = pytest.mark.skipif(
    not _probe_db_available(),
    reason=f"local Postgres not reachable for integration tests ({_DB_PROBE_ERROR})",
)


async def _make_test_user(session) -> uuid.UUID:
    """Insert a throw-away user and return its id. Caller is responsible for
    cleaning up via cascade (deleting the user wipes their entities + edges).
    """
    from app.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"entity-extractor-test-{uuid.uuid4()}@example.invalid",
    )
    session.add(user)
    await session.flush()
    return user.id


async def _cleanup_user(user_id: uuid.UUID) -> None:
    """Best-effort cleanup. Relationships cascade from entities/users/tasks,
    so deleting the user is enough; but the User model has no on-delete
    cascade for entities, so we drop them explicitly first."""
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models import Entity, Relationship, User

    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                await s.execute(delete(Relationship).where(Relationship.user_id == user_id))
                await s.execute(delete(Entity).where(Entity.user_id == user_id))
                await s.execute(delete(User).where(User.id == user_id))
    except Exception:
        # Tests are isolated by per-run UUIDs; leaking a row is annoying but
        # not fatal to subsequent runs.
        pass


@pytest.fixture
def db_user():
    """Yields a fresh test user_id; cleans up entities/relationships/user on teardown."""
    from app.db.session import AsyncSessionLocal

    async def _make() -> uuid.UUID:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                return await _make_test_user(s)

    uid = asyncio.run(_make())
    yield uid
    asyncio.run(_cleanup_user(uid))


@_db_required
class TestUpsertPersonEntity:
    def test_creates_new_entity_when_absent(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Entity
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    eid = await upsert_person_entity(
                        s, user_id=db_user, canonical="Hương", raw_alias="Bạn Hương"
                    )
                async with s.begin():
                    row = (
                        await s.execute(
                            select(Entity).where(Entity.id == eid)
                        )
                    ).scalar_one()
                    return row.canonical_name, list(row.aliases)

        canonical, aliases = asyncio.run(_go())
        assert canonical == "Hương"
        assert "Bạn Hương" in aliases

    def test_reuses_existing_entity_and_returns_same_id(self, db_user):
        from app.db.session import AsyncSessionLocal

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    eid1 = await upsert_person_entity(s, user_id=db_user, canonical="Minh")
                async with s.begin():
                    eid2 = await upsert_person_entity(s, user_id=db_user, canonical="Minh")
                return eid1, eid2

        eid1, eid2 = asyncio.run(_go())
        assert eid1 == eid2

    def test_appends_alias_only_when_new(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Entity
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    eid = await upsert_person_entity(
                        s, user_id=db_user, canonical="Đỗ", raw_alias="anh Đỗ"
                    )
                async with s.begin():
                    # Re-upsert with a different alias → append.
                    await upsert_person_entity(
                        s, user_id=db_user, canonical="Đỗ", raw_alias="bác Đỗ"
                    )
                async with s.begin():
                    # Re-upsert with an alias that already exists → no-op.
                    await upsert_person_entity(
                        s, user_id=db_user, canonical="Đỗ", raw_alias="anh Đỗ"
                    )
                async with s.begin():
                    row = (
                        await s.execute(select(Entity).where(Entity.id == eid))
                    ).scalar_one()
                    return list(row.aliases)

        aliases = asyncio.run(_go())
        # Order matters: append-in-encounter-order; no duplicates.
        assert aliases == ["anh Đỗ", "bác Đỗ"]

    def test_alias_equal_to_canonical_is_not_added(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Entity
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    await upsert_person_entity(
                        s, user_id=db_user, canonical="Solo", raw_alias="Solo"
                    )
                async with s.begin():
                    row = (
                        await s.execute(
                            select(Entity).where(
                                Entity.user_id == db_user,
                                Entity.canonical_name == "Solo",
                            )
                        )
                    ).scalar_one()
                    return list(row.aliases)

        aliases = asyncio.run(_go())
        assert aliases == []

    def test_empty_canonical_raises(self, db_user):
        from app.db.session import AsyncSessionLocal

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    await upsert_person_entity(s, user_id=db_user, canonical="")

        with pytest.raises(ValueError):
            asyncio.run(_go())


async def _make_test_task(session, user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a throw-away SourceDocument + Task. Returns (task_id, source_doc_id)."""
    import hashlib

    from app.models import SourceDocument, Task

    doc = SourceDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        source_type="test",
        source_ref=f"entity-extractor-{uuid.uuid4()}",
        content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
    )
    session.add(doc)
    await session.flush()
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        source_doc_id=doc.id,
        title="Test task",
    )
    session.add(task)
    await session.flush()
    return task.id, doc.id


@_db_required
class TestRefreshTaskRelationships:
    def test_inserts_assigned_to_and_mentioned_in(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Relationship
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    task_id, doc_id = await _make_test_task(s, db_user)
                    eid_a = await upsert_person_entity(s, user_id=db_user, canonical="Mary")
                    eid_b = await upsert_person_entity(s, user_id=db_user, canonical="John")
                    inserted = await refresh_task_relationships(
                        s,
                        user_id=db_user,
                        task_id=task_id,
                        assignee_entity_id=eid_a,
                        mentioned_entity_ids=[eid_b],
                        source_doc_id=doc_id,
                    )
                async with s.begin():
                    rows = (
                        await s.execute(
                            select(Relationship).where(Relationship.to_task_id == task_id)
                        )
                    ).scalars().all()
                    return inserted, sorted((r.relationship_type, r.from_entity_id) for r in rows), eid_a, eid_b

        inserted, rows, eid_a, eid_b = asyncio.run(_go())
        assert inserted == 2
        assert rows == sorted([("assigned_to", eid_a), ("mentioned_in", eid_b)])

    def test_idempotent_replace_per_task(self, db_user):
        """Running refresh twice on the same task results in exactly the edge
        set from the second call — no duplicates."""
        from app.db.session import AsyncSessionLocal
        from app.models import Relationship
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    task_id, doc_id = await _make_test_task(s, db_user)
                    eid_a = await upsert_person_entity(s, user_id=db_user, canonical="A")
                    eid_b = await upsert_person_entity(s, user_id=db_user, canonical="B")
                    eid_c = await upsert_person_entity(s, user_id=db_user, canonical="C")
                    # First run: assignee A, mentioned B
                    await refresh_task_relationships(
                        s,
                        user_id=db_user,
                        task_id=task_id,
                        assignee_entity_id=eid_a,
                        mentioned_entity_ids=[eid_b],
                        source_doc_id=doc_id,
                    )
                    # Second run: assignee C, mentioned A
                    await refresh_task_relationships(
                        s,
                        user_id=db_user,
                        task_id=task_id,
                        assignee_entity_id=eid_c,
                        mentioned_entity_ids=[eid_a],
                        source_doc_id=doc_id,
                    )
                async with s.begin():
                    rows = (
                        await s.execute(
                            select(Relationship).where(Relationship.to_task_id == task_id)
                        )
                    ).scalars().all()
                    return sorted((r.relationship_type, r.from_entity_id) for r in rows), eid_a, eid_c

        rows, eid_a, eid_c = asyncio.run(_go())
        assert rows == sorted([("assigned_to", eid_c), ("mentioned_in", eid_a)])

    def test_skips_mention_that_duplicates_assignee(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Relationship
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    task_id, doc_id = await _make_test_task(s, db_user)
                    eid = await upsert_person_entity(s, user_id=db_user, canonical="Solo")
                    inserted = await refresh_task_relationships(
                        s,
                        user_id=db_user,
                        task_id=task_id,
                        assignee_entity_id=eid,
                        mentioned_entity_ids=[eid],  # duplicate
                        source_doc_id=doc_id,
                    )
                async with s.begin():
                    rows = (
                        await s.execute(
                            select(Relationship).where(Relationship.to_task_id == task_id)
                        )
                    ).scalars().all()
                    return inserted, [(r.relationship_type, r.from_entity_id) for r in rows], eid

        inserted, rows, eid = asyncio.run(_go())
        assert inserted == 1
        assert rows == [("assigned_to", eid)]

    def test_owned_types_only_deletes_assigned_and_mentioned(self, db_user):
        """A simulated Phase-2 'depends_on' edge for the same task must survive
        a refresh."""
        from app.db.session import AsyncSessionLocal
        from app.models import Relationship
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    task_id, doc_id = await _make_test_task(s, db_user)
                    eid_a = await upsert_person_entity(s, user_id=db_user, canonical="A")
                    eid_b = await upsert_person_entity(s, user_id=db_user, canonical="B")
                    # Insert a synthetic non-owned edge type directly.
                    s.add(
                        Relationship(
                            id=uuid.uuid4(),
                            user_id=db_user,
                            from_entity_id=eid_a,
                            to_task_id=task_id,
                            relationship_type="depends_on",
                            source_doc_id=doc_id,
                        )
                    )
                    await s.flush()
                    await refresh_task_relationships(
                        s,
                        user_id=db_user,
                        task_id=task_id,
                        assignee_entity_id=eid_b,
                        mentioned_entity_ids=[],
                        source_doc_id=doc_id,
                    )
                async with s.begin():
                    rows = (
                        await s.execute(
                            select(Relationship).where(Relationship.to_task_id == task_id)
                        )
                    ).scalars().all()
                    return sorted((r.relationship_type, r.from_entity_id) for r in rows), eid_a, eid_b

        rows, eid_a, eid_b = asyncio.run(_go())
        assert rows == sorted([("assigned_to", eid_b), ("depends_on", eid_a)])


@_db_required
class TestUpdateEntityGraphOrchestrator:
    def test_end_to_end_two_pass(self, db_user):
        """assignee gets assigned_to; another known canonical mentioned in
        text gets mentioned_in."""
        from app.db.session import AsyncSessionLocal
        from app.models import Entity, Relationship
        from sqlalchemy import select

        async def _go():
            # Two tasks. Both share an assignee pool that grows in pass 1:
            #   T1: assignee=Hương, text mentions Minh
            #   T2: assignee=Minh, text mentions Hương + Đỗ (Đỗ never an
            #       assignee → not in pool → not mentioned)
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    t1_id, doc1 = await _make_test_task(s, db_user)
                    t2_id, _ = await _make_test_task(s, db_user)
                    summary = await update_entity_graph_for_tasks(
                        s,
                        user_id=db_user,
                        tasks=[
                            {
                                "id": t1_id,
                                "title": "Discuss budget with Minh",
                                "description": None,
                                "assignee": "Bạn Hương",
                                "assignee_canonical": "Hương",
                                "evidence_quote": None,
                            },
                            {
                                "id": t2_id,
                                "title": "Send report to Hương and Đỗ",
                                "description": None,
                                "assignee": "Minh",
                                "assignee_canonical": "Minh",
                                "evidence_quote": None,
                            },
                        ],
                        source_doc_id=doc1,
                    )
                async with s.begin():
                    ents = (
                        await s.execute(
                            select(Entity).where(
                                Entity.user_id == db_user,
                                Entity.entity_type == PERSON_ENTITY_TYPE,
                            )
                        )
                    ).scalars().all()
                    rels = (
                        await s.execute(
                            select(Relationship).where(Relationship.user_id == db_user)
                        )
                    ).scalars().all()
                    return summary, sorted(e.canonical_name for e in ents), rels, t1_id, t2_id

        summary, canonicals, rels, t1_id, t2_id = asyncio.run(_go())
        # Two assignees upserted (Hương, Minh). Đỗ was not assignee → not added.
        assert summary["entities_upserted"] == 2
        assert canonicals == ["Hương", "Minh"]
        edges = sorted((r.relationship_type, r.to_task_id) for r in rels)
        # Expect: T1: assigned_to(Hương) + mentioned_in(Minh)
        #         T2: assigned_to(Minh) + mentioned_in(Hương)
        assert edges == sorted(
            [
                ("assigned_to", t1_id),
                ("mentioned_in", t1_id),
                ("assigned_to", t2_id),
                ("mentioned_in", t2_id),
            ]
        )
        # And total emitted relationships match what the summary said.
        assert summary["relationships_emitted"] == 4

    def test_empty_input_no_op(self, db_user):
        from app.db.session import AsyncSessionLocal

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    return await update_entity_graph_for_tasks(
                        s, user_id=db_user, tasks=[], source_doc_id=None
                    )

        summary = asyncio.run(_go())
        assert summary == {"entities_upserted": 0, "relationships_emitted": 0}

    def test_task_without_assignee_gets_no_assigned_to_edge(self, db_user):
        from app.db.session import AsyncSessionLocal
        from app.models import Relationship
        from sqlalchemy import select

        async def _go():
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    tid, doc = await _make_test_task(s, db_user)
                    summary = await update_entity_graph_for_tasks(
                        s,
                        user_id=db_user,
                        tasks=[
                            {
                                "id": tid,
                                "title": "Some task",
                                "description": None,
                                "assignee": None,
                                "assignee_canonical": None,
                                "evidence_quote": None,
                            }
                        ],
                        source_doc_id=doc,
                    )
                async with s.begin():
                    rels = (
                        await s.execute(
                            select(Relationship).where(Relationship.to_task_id == tid)
                        )
                    ).scalars().all()
                    return summary, rels

        summary, rels = asyncio.run(_go())
        assert summary["entities_upserted"] == 0
        assert rels == []


# Diagnostic surface: keep a sanity-check that ``_OWNED_RELATIONSHIP_TYPES``
# stays in lockstep with the docstring / contract — a refactor that adds a
# new owned type must update both. Cheap, runs always.
def test_owned_relationship_types_are_assigned_to_and_mentioned_in():
    assert _OWNED_RELATIONSHIP_TYPES == ("assigned_to", "mentioned_in")
