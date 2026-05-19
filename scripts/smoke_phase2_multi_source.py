"""Phase 2.2 multi-source conflict smoke test.

The eval dataset has no cross-source samples (each row is single-source),
so the multi-source detector cannot be measured through run_eval. This
script seeds the DB with a controlled state that *does* span platforms
(Gmail thread + Drive doc with overlapping deliverables), then drives the
real ``validate_tasks`` node and asserts on the conflict events it emits.

Cases:
  1. Happy path — new Gmail task whose existing Drive sibling shares the
     same deliverable AND the same person entity → ``scope="multi_source"``
  2. Same source_type — existing task is *another* Gmail doc → no
     multi_source emission (cross-platform requirement)
  3. Below title threshold — Drive sibling with a very different title →
     no emission
  4. Outside lookback window — Drive sibling 45 days old → no emission

Run:
    DATABASE_URL="postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot" \
        python scripts/smoke_phase2_multi_source.py
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot",
)
os.environ.setdefault("ENCRYPTION_KEY", "x" * 32)
os.environ.setdefault("GROQ_API_KEY", "smoke-test-not-used")
os.environ.setdefault("GMAIL_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("DRIVE_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("CALENDAR_MCP_URL", "https://smoke.invalid")
os.environ.setdefault("BACKEND_API_BASE_URL", "http://smoke.invalid")
os.environ.setdefault("GOOGLE_CLIENT_ID", "smoke")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "smoke")
os.environ.setdefault("LANGSMITH_TRACING", "false")
# Skip LLM-based conflict checks (intra-batch / inter-doc) — multi-source is
# pure-logic and doesn't need them. This also dodges the dummy GROQ_API_KEY
# above which would otherwise raise on the LLM call.
os.environ.setdefault("EVAL_ENABLE_CONFLICT_CHECK", "0")

from sqlalchemy import delete, select, update  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models import Entity, Relationship, SourceDocument, Task, User  # noqa: E402
from app.pipeline.nodes.validate_tasks import validate_tasks  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────


async def _make_user() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = User(id=uuid.uuid4(), email=f"smoke-phase2-{uuid.uuid4()}@example.invalid")
            s.add(u)
            await s.flush()
            return u.id


async def _make_doc(user_id: uuid.UUID, source_type: str) -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        async with s.begin():
            d = SourceDocument(
                id=uuid.uuid4(),
                user_id=user_id,
                source_type=source_type,
                source_ref=f"smoke-{source_type}-{uuid.uuid4()}",
                content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                raw_text="(smoke seed)",
            )
            s.add(d)
            await s.flush()
            return d.id


async def _make_task_with_assignee(
    user_id: uuid.UUID,
    source_doc_id: uuid.UUID,
    *,
    title: str,
    assignee_canonical: str,
    created_offset_days: int = 0,
) -> uuid.UUID:
    """Insert task + person entity + assigned_to relationship."""
    async with AsyncSessionLocal() as s:
        async with s.begin():
            tid = uuid.uuid4()
            s.add(
                Task(
                    id=tid,
                    user_id=user_id,
                    source_doc_id=source_doc_id,
                    title=title,
                    assignee=assignee_canonical,
                    assignee_canonical=assignee_canonical,
                )
            )
            await s.flush()
            if created_offset_days:
                shifted = datetime.now(UTC) - timedelta(days=created_offset_days)
                await s.execute(update(Task).where(Task.id == tid).values(created_at=shifted))
            eid = uuid.uuid4()
            s.add(
                Entity(
                    id=eid,
                    user_id=user_id,
                    entity_type="person",
                    canonical_name=assignee_canonical,
                    aliases=[],
                )
            )
            await s.flush()
            s.add(
                Relationship(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    from_entity_id=eid,
                    to_task_id=tid,
                    relationship_type="assigned_to",
                    source_doc_id=source_doc_id,
                )
            )
            await s.flush()
            return tid


async def _cleanup(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(Relationship).where(Relationship.user_id == user_id))
            await s.execute(delete(Entity).where(Entity.user_id == user_id))
            await s.execute(delete(Task).where(Task.user_id == user_id))
            await s.execute(delete(SourceDocument).where(SourceDocument.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))


def _new_gmail_state(user_id: uuid.UUID, source_doc_id: uuid.UUID, *, title: str) -> dict:
    """Build the PipelineState that ``validate_tasks`` consumes — a single
    new Gmail task ready for cross-source comparison."""
    return {
        "user_id": str(user_id),
        "source_doc_id": str(source_doc_id),
        "source_type": "gmail",
        "cleaned_text": f"Reminder for: {title}",
        "normalized_tasks": [
            {
                "title": title,
                "assignee": "Hương",
                "assignee_canonical": "Hương",
                "deadline": "2026-06-30",
                "confidence": 0.9,
                "source_ref": "email-1",
            }
        ],
        "existing_tasks": [],
        "errors": [],
        "metadata": {"sent_at": "2026-05-18"},
    }


def _multi_source_conflicts(result: dict) -> list[dict]:
    return [c for c in result.get("conflicts", []) if c.get("scope") == "multi_source"]


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  ❌ ASSERT FAIL: {msg}")
        raise SystemExit(1)
    print(f"  ✅ {msg}")


# ── Cases ──────────────────────────────────────────────────────────────────────


async def case_happy_path(user_id: uuid.UUID) -> None:
    print("\n--- Case 1: happy path (Gmail new + Drive existing, same deliverable) ---")
    drive_doc = await _make_doc(user_id, "drive")
    gmail_doc = await _make_doc(user_id, "gmail")
    await _make_task_with_assignee(
        user_id,
        drive_doc,
        title="Submit Q2 financial report",
        assignee_canonical="Hương",
    )
    state = _new_gmail_state(user_id, gmail_doc, title="Submit Q2 financial report")
    result = validate_tasks(state)
    ms = _multi_source_conflicts(result)
    _expect(len(ms) == 1, f"exactly 1 multi_source conflict emitted (got {len(ms)})")
    _expect(ms[0]["source_b_ref"] == str(drive_doc), "source_b_ref carries Drive doc id")
    _expect(
        "drive" in ms[0]["description"].lower() and "gmail" in ms[0]["description"].lower(),
        "description names both platforms",
    )
    _expect(
        not any("multi-source" in e.lower() for e in result.get("errors", [])),
        "no loader/detector errors logged",
    )


async def case_same_source_type(user_id: uuid.UUID) -> None:
    print("\n--- Case 2: same source_type (Gmail vs Gmail) → no emission ---")
    other_gmail = await _make_doc(user_id, "gmail")
    cur_gmail = await _make_doc(user_id, "gmail")
    await _make_task_with_assignee(
        user_id,
        other_gmail,
        title="Submit Q2 financial report",
        assignee_canonical="Hương",
    )
    state = _new_gmail_state(user_id, cur_gmail, title="Submit Q2 financial report")
    result = validate_tasks(state)
    ms = _multi_source_conflicts(result)
    _expect(len(ms) == 0, "no multi_source conflict (same source_type filter blocks it)")


async def case_below_title_threshold(user_id: uuid.UUID) -> None:
    print("\n--- Case 3: title similarity below 0.85 → no emission ---")
    drive_doc = await _make_doc(user_id, "drive")
    gmail_doc = await _make_doc(user_id, "gmail")
    # Same assignee but totally unrelated title.
    await _make_task_with_assignee(
        user_id,
        drive_doc,
        title="Plan team offsite",
        assignee_canonical="Hương",
    )
    state = _new_gmail_state(user_id, gmail_doc, title="Submit Q2 financial report")
    result = validate_tasks(state)
    ms = _multi_source_conflicts(result)
    _expect(len(ms) == 0, "no multi_source conflict when titles dissimilar")


async def case_outside_lookback(user_id: uuid.UUID) -> None:
    print("\n--- Case 4: existing task 45 days old → no emission (outside 30d window) ---")
    drive_doc = await _make_doc(user_id, "drive")
    gmail_doc = await _make_doc(user_id, "gmail")
    await _make_task_with_assignee(
        user_id,
        drive_doc,
        title="Submit Q2 financial report",
        assignee_canonical="Hương",
        created_offset_days=45,
    )
    state = _new_gmail_state(user_id, gmail_doc, title="Submit Q2 financial report")
    result = validate_tasks(state)
    ms = _multi_source_conflicts(result)
    _expect(len(ms) == 0, "no multi_source conflict for stale candidate")


# ── Main ───────────────────────────────────────────────────────────────────────


async def main() -> int:
    print("== Phase 2.2 multi-source conflict smoke test ==")
    print(f"DATABASE_URL = {os.environ.get('DATABASE_URL')}")
    print(f"Started at  = {datetime.now(UTC).isoformat()}")
    # Each case uses its own user_id so the lookback / type filters are
    # tested in isolation (no cross-case contamination of the entity pool).
    for label, fn in [
        ("happy_path", case_happy_path),
        ("same_source_type", case_same_source_type),
        ("below_title_threshold", case_below_title_threshold),
        ("outside_lookback", case_outside_lookback),
    ]:
        user_id = await _make_user()
        try:
            await fn(user_id)
        finally:
            await _cleanup(user_id)
            print(f"  (cleaned up user {user_id})")
    print("\n== ALL CASES PASSED ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
