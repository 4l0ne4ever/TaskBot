"""Phase 1 entity-graph smoke test.

Exercises the real ``save_tasks_service.async_save_tasks`` path (the same
convergence point used by Gmail/Drive/upload syncs) with realistic
``PipelineState`` payloads, then queries the DB to verify:

  - Person entities are upserted from each task's ``assignee_canonical``.
  - ``assigned_to`` + ``mentioned_in`` relationships are emitted with
    ``source_doc_id`` provenance.
  - Idempotency: a second run with the same payload does NOT duplicate
    entities or relationships; aliases accumulate when new raw forms appear.
  - Edge cases: assignee=None task gets no ``assigned_to`` edge; mutual
    mentions across two persons produce the expected 4 edges.

Run:
    DATABASE_URL="postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot" \
        python scripts/smoke_phase1_entity_graph.py

Exits non-zero if any assertion fails. Output is a markdown-ready summary
suitable for ``docs/phase-1-smoke-test.md``.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

# Default DB URL to the Docker mapping if caller didn't set it.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot",
)
# Required by config; tests never make a real LLM call here.
os.environ.setdefault("ENCRYPTION_KEY", "x" * 32)
os.environ.setdefault("GROQ_API_KEY", "smoke-test-not-used")
os.environ.setdefault("GMAIL_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("DRIVE_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("CALENDAR_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("BACKEND_API_BASE_URL", "http://smoke.invalid")
os.environ.setdefault("GOOGLE_CLIENT_ID", "smoke")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "smoke")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from sqlalchemy import delete, select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Conflict,
    Entity,
    PipelineRun,
    Relationship,
    SourceDocument,
    Task,
    User,
)
from app.services.save_tasks_service import async_save_tasks  # noqa: E402

# ── Test fixtures ──────────────────────────────────────────────────────────────


async def _make_user_and_doc() -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(
                id=uuid.uuid4(),
                email=f"smoke-phase1-{uuid.uuid4()}@example.invalid",
            )
            s.add(user)
            await s.flush()
            doc = SourceDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                source_type="gmail",
                source_ref=f"smoke-{uuid.uuid4()}",
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(smoke test)",
            )
            s.add(doc)
            await s.flush()
            return user.id, doc.id


async def _cleanup(user_id: uuid.UUID) -> None:
    """Drop everything we created for this run. Order matters because tasks/
    relationships have FKs."""
    async with AsyncSessionLocal() as s:
        async with s.begin():
            # Relationships and pipeline_runs cascade-clean from tasks/users in
            # general, but we delete explicitly to keep the script self-contained
            # even if other FK strategies change.
            await s.execute(delete(Relationship).where(Relationship.user_id == user_id))
            await s.execute(delete(Conflict).where(Conflict.user_id == user_id))
            await s.execute(delete(Task).where(Task.user_id == user_id))
            await s.execute(delete(PipelineRun).where(PipelineRun.user_id == user_id))
            await s.execute(delete(Entity).where(Entity.user_id == user_id))
            await s.execute(delete(SourceDocument).where(SourceDocument.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))


def _make_validated_tasks() -> list[dict]:
    """Three realistic VN/EN tasks that exercise:
      - assigned_to + mentioned_in (mutual mentions)
      - alias accumulation (raw vs canonical)
      - non-assignee mentions (Đỗ only appears in text — won't be added since
        he is never an assignee in this batch)
    """
    return [
        {
            "title": "Chuẩn bị slide thuyết trình",
            "description": "Phối hợp với Minh để gửi link cho Đỗ",
            "assignee": "Bạn Hương",
            "assignee_canonical": "Hương",
            "deadline": "2026-06-01",
            "deadline_v2": {
                "iso": "2026-06-01",
                "type": "exact",
                "text": "ngày 1 tháng 6",
                "phrase_class": "absolute",
                "phrase_params": None,
                "source": "llm",
                "confidence": 0.9,
                "is_ambiguous": False,
            },
            "priority": None,
            "uncertainty": None,
            "missing_fields": [],
            "evidence_quote": "chuẩn bị slide thuyết trình",
            "confidence": 0.9,
            "abstained": False,
        },
        {
            "title": "Review bản kế hoạch dự án",
            "description": "Hương đã prepare draft, Minh review",
            "assignee": "Minh",
            "assignee_canonical": "Minh",
            "deadline": "2026-06-02",
            "deadline_v2": {
                "iso": "2026-06-02",
                "type": "exact",
                "text": "ngày 2 tháng 6",
                "phrase_class": "absolute",
                "phrase_params": None,
                "source": "llm",
                "confidence": 0.9,
                "is_ambiguous": False,
            },
            "priority": None,
            "uncertainty": None,
            "missing_fields": [],
            "evidence_quote": "review bản kế hoạch",
            "confidence": 0.9,
            "abstained": False,
        },
        {
            "title": "Đăng ký phòng họp",
            "description": "Cuộc họp tuần sau",
            "assignee": None,
            "assignee_canonical": None,
            "deadline": None,
            "deadline_v2": {
                "iso": None,
                "type": "none",
                "text": None,
                "phrase_class": "none",
                "phrase_params": None,
                "source": "llm",
                "confidence": 0.8,
                "is_ambiguous": False,
            },
            "priority": None,
            "uncertainty": None,
            "missing_fields": ["assignee"],
            "evidence_quote": None,
            "confidence": 0.8,
            "abstained": False,
        },
    ]


# ── Probes ─────────────────────────────────────────────────────────────────────


async def _probe(user_id: uuid.UUID) -> dict:
    """Snapshot what's in the DB for this user."""
    async with AsyncSessionLocal() as s:
        ents = (
            await s.execute(
                select(Entity).where(Entity.user_id == user_id)
            )
        ).scalars().all()
        rels = (
            await s.execute(
                select(Relationship).where(Relationship.user_id == user_id)
            )
        ).scalars().all()
        tasks = (
            await s.execute(
                select(Task).where(Task.user_id == user_id)
            )
        ).scalars().all()
        return {
            "entities": [
                {
                    "id": str(e.id),
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type,
                    "aliases": list(e.aliases or []),
                }
                for e in ents
            ],
            "relationships": [
                {
                    "from_entity_id": str(r.from_entity_id),
                    "to_task_id": str(r.to_task_id) if r.to_task_id else None,
                    "to_entity_id": str(r.to_entity_id) if r.to_entity_id else None,
                    "relationship_type": r.relationship_type,
                    "source_doc_id": str(r.source_doc_id) if r.source_doc_id else None,
                }
                for r in rels
            ],
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "assignee_canonical": t.assignee_canonical,
                }
                for t in tasks
            ],
        }


# ── Assertions ─────────────────────────────────────────────────────────────────


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  ❌ ASSERT FAIL: {msg}")
        raise SystemExit(1)
    print(f"  ✅ {msg}")


# ── Main flow ──────────────────────────────────────────────────────────────────


async def main() -> int:
    print("== Phase 1 entity-graph smoke test ==")
    print(f"DATABASE_URL = {os.environ.get('DATABASE_URL')}")
    print(f"Started at  = {datetime.now(UTC).isoformat()}")

    user_id, doc_id = await _make_user_and_doc()
    print(f"\nTest user_id      = {user_id}")
    print(f"Test source_doc_id = {doc_id}")

    try:
        # ── Run 1: initial extraction ──────────────────────────────────────
        print("\n--- Run 1: initial extraction ---")
        validated = _make_validated_tasks()
        state1 = {
            "user_id": str(user_id),
            "source_doc_id": str(doc_id),
            "validated_tasks": validated,
            "conflicts": [],
            "errors": [],
            "metadata": {"dedupe_group_id": "smoke-phase1-thread"},
        }
        result1 = await async_save_tasks(state1)
        print(f"  saved_task_ids: {len(result1['saved_task_ids'])} tasks")
        for e in result1.get("errors", []):
            print(f"  errors: {e}")
        _expect(
            len(result1["saved_task_ids"]) == 3,
            "3 tasks saved on Run 1",
        )
        _expect(
            not any("entity_extractor" in e for e in result1.get("errors", [])),
            "no entity_extractor errors logged",
        )

        snap1 = await _probe(user_id)
        ent_names1 = sorted(e["canonical_name"] for e in snap1["entities"])
        _expect(
            ent_names1 == ["Hương", "Minh"],
            f"entities = ['Hương', 'Minh'] (got {ent_names1})",
        )
        huong = next(e for e in snap1["entities"] if e["canonical_name"] == "Hương")
        _expect(
            "Bạn Hương" in huong["aliases"],
            f"Hương.aliases contains 'Bạn Hương' (got {huong['aliases']})",
        )
        minh = next(e for e in snap1["entities"] if e["canonical_name"] == "Minh")
        _expect(
            minh["aliases"] == [],
            f"Minh.aliases empty since raw==canonical (got {minh['aliases']})",
        )

        rel_types1 = sorted(r["relationship_type"] for r in snap1["relationships"])
        # Expected edges (3 tasks):
        #   T1 (Hương assignee, text mentions Minh): assigned_to + mentioned_in
        #   T2 (Minh assignee, text mentions Hương): assigned_to + mentioned_in
        #   T3 (no assignee, text mentions no one):  0 edges
        _expect(
            rel_types1 == ["assigned_to", "assigned_to", "mentioned_in", "mentioned_in"],
            f"4 edges: 2 assigned_to + 2 mentioned_in (got {rel_types1})",
        )
        _expect(
            all(r["source_doc_id"] == str(doc_id) for r in snap1["relationships"]),
            "all relationships carry source_doc_id provenance",
        )

        # ── Run 2: idempotent re-run (same payload) ────────────────────────
        print("\n--- Run 2: idempotent re-run ---")
        state2 = {
            "user_id": str(user_id),
            "source_doc_id": str(doc_id),
            "validated_tasks": validated,  # same list of dicts
            "conflicts": [],
            "errors": [],
            "metadata": {"dedupe_group_id": "smoke-phase1-thread"},
        }
        result2 = await async_save_tasks(state2)
        snap2 = await _probe(user_id)
        ent_names2 = sorted(e["canonical_name"] for e in snap2["entities"])
        _expect(
            ent_names2 == ent_names1,
            "Run 2: entity set unchanged (no duplicates)",
        )
        # Entity UUIDs stable across runs
        entity_id_map_1 = {e["canonical_name"]: e["id"] for e in snap1["entities"]}
        entity_id_map_2 = {e["canonical_name"]: e["id"] for e in snap2["entities"]}
        _expect(
            entity_id_map_1 == entity_id_map_2,
            "Run 2: entity UUIDs stable (upsert reused existing rows)",
        )
        _expect(
            len(snap2["relationships"]) == len(snap1["relationships"]),
            "Run 2: relationship count unchanged",
        )

        # ── Run 3: new alias appears for Hương ─────────────────────────────
        print("\n--- Run 3: new raw alias for existing canonical ---")
        validated3 = _make_validated_tasks()
        validated3[0] = dict(validated3[0])
        validated3[0]["assignee"] = "Chị Hương"  # different raw form, same canonical
        state3 = {
            "user_id": str(user_id),
            "source_doc_id": str(doc_id),
            "validated_tasks": validated3,
            "conflicts": [],
            "errors": [],
            "metadata": {"dedupe_group_id": "smoke-phase1-thread"},
        }
        await async_save_tasks(state3)
        snap3 = await _probe(user_id)
        huong3 = next(e for e in snap3["entities"] if e["canonical_name"] == "Hương")
        _expect(
            "Bạn Hương" in huong3["aliases"] and "Chị Hương" in huong3["aliases"],
            f"Hương.aliases now has both 'Bạn Hương' and 'Chị Hương' (got {huong3['aliases']})",
        )
        _expect(
            len([e for e in snap3["entities"] if e["canonical_name"] == "Hương"]) == 1,
            "Still exactly one Hương entity (no duplicate from new alias)",
        )

        # ── Final summary ──────────────────────────────────────────────────
        print("\n== ALL CHECKS PASSED ==")
        print(f"Final state for user {user_id}:")
        print(f"  Entities ({len(snap3['entities'])}):")
        for e in snap3["entities"]:
            print(f"    - {e['canonical_name']} ({e['entity_type']}) aliases={e['aliases']}")
        print(f"  Relationships ({len(snap3['relationships'])}):")
        for r in snap3["relationships"]:
            print(f"    - {r['relationship_type']}: {r['from_entity_id'][:8]}… → task {(r['to_task_id'] or '')[:8]}…")
        print(f"  Tasks ({len(snap3['tasks'])}):")
        for t in snap3["tasks"]:
            print(f"    - {t['title']} (assignee={t['assignee_canonical']})")
        return 0
    finally:
        await _cleanup(user_id)
        print(f"\nCleanup complete for user {user_id}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
