"""Cross-thread dedup tests (2026-06-07).

When a task is mentioned across two distinct Gmail threads (different
``dedupe_group_id``), the in-group dedup path doesn't find a candidate
and a duplicate row used to be created. ``save_tasks_service`` now also
searches the user's recent active tasks for a title-similar + assignee-
matching candidate at a stricter title-similarity threshold (default
0.94) and reuses it instead.

Coverage:

  Reuse (positive, dedup engages):
    - same title + same assignee across 2 threads → 1 row
    - VN accented assignee ("Lê Minh Đức" vs "lê minh đức") → 1 row
    - 3-thread cascade (same task across 3 threads) → 1 row
    - prior confirmed task with future deadline → still eligible → 1 row

  No-reuse (negative, dedup correctly skips):
    - neighbour titles ("Submit Q1 report" vs "Submit Q2 report") → 2 rows
      (SequenceMatcher = 0.9375, below the 0.94 threshold)
    - different assignee → 2 rows (SQL pre-filter blocks)
    - prior task ``progress_state='done'`` → 2 rows (excluded from pool)
    - prior task ``status='dismissed'`` → 2 rows (excluded from pool)
    - incoming assignee empty → 2 rows (no candidate-assignee set → skip)

What this set explicitly does NOT cover (v0 limitations, documented in
``failure-mode-analysis.md`` §7):

    - 30-day lookback boundary (created_at not seedable from outside the
      service; would need direct UPDATE bypassing typed assertion path)
    - real Gmail thread HTML headers (covered by e2e + manual sync verify)
    - calendar-event side effects (orphan recurring events; that's a
      dispatch-node concern, not save_tasks_service)
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


async def _seed_user_and_first_task(
    *,
    title: str,
    assignee: str,
    group: str,
    progress_state: str | None = None,
    status: str = "pending",
    deadline=None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    from app.db.session import AsyncSessionLocal
    from app.models import SourceDocument, Task, User

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = User(id=uuid.uuid4(), email=f"ct-{uuid.uuid4()}@example.invalid")
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
                title=title,
                assignee=assignee,
                status=status,
                progress_state=progress_state,
                deadline=deadline,
            )
            s.add(task)
            await s.flush()
            return user.id, doc.id, task.id


async def _add_new_thread_doc(user_id: uuid.UUID, group: str) -> uuid.UUID:
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
                raw_text="(second thread)",
            )
            s.add(doc)
            await s.flush()
            return doc.id


async def _count_tasks(user_id: uuid.UUID) -> int:
    from sqlalchemy import select, func
    from app.db.session import AsyncSessionLocal
    from app.models import Task

    async with AsyncSessionLocal() as s:
        n = (await s.execute(select(func.count()).where(Task.user_id == user_id))).scalar_one()
        return int(n or 0)


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


def _state(
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    *,
    title: str,
    assignee: str,
    group: str,
) -> dict:
    return {
        "user_id": str(user_id),
        "source_doc_id": str(doc_id),
        "validated_tasks": [
            {
                "title": title,
                "assignee": assignee,
                "deadline": "2026-06-30",
                "decision_band": "accept",
                "abstained": False,
                "missing_fields": [],
                "source_ref": "email-cross-thread",
            }
        ],
        "conflicts": [],
        "errors": [],
        "metadata": {"sent_at": "2026-06-01", "dedupe_group_id": group},
    }


# ── positive: cross-thread reuse happens ─────────────────────────────────


@_db_required
def test_cross_thread_same_title_and_assignee_reuses_row():
    """Two emails about the same task in different Gmail threads should
    land in a single row (cross-thread title-similarity ≥ 0.92)."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Draft the Henderson client proposal",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Draft the Henderson client proposal",
                assignee="Emily",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        # Reuse → still 1 task row, not 2.
        assert asyncio.run(_count_tasks(user_id)) == 1
        # The saved id is the original row's id (in-place update).
        assert str(task_id) in out.get("saved_task_ids", [])
    finally:
        asyncio.run(_cleanup(user_id))


# ── negative: neighbour titles must NOT merge ────────────────────────────


@_db_required
def test_cross_thread_neighbour_titles_do_not_merge():
    """``Submit Q1 report`` and ``Submit Q2 report`` differ by one token —
    SequenceMatcher gives 0.9375. The cross-thread threshold is 0.94 so
    these distinct deliverables stay distinct. If the threshold drops
    below 0.94, this test breaks — the trade-off needs revisiting."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, _task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Submit Q1 report",
            assignee="Lê Minh Đức",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Submit Q2 report",
                assignee="Lê Minh Đức",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        assert asyncio.run(_count_tasks(user_id)) == 2
    finally:
        asyncio.run(_cleanup(user_id))


# ── negative: assignee mismatch blocks merge ─────────────────────────────


@_db_required
def test_cross_thread_assignee_mismatch_blocks_merge():
    """Different assignees should NEVER merge regardless of title
    similarity — the SQL pre-filter requires assignee match."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, _task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Review Q2 deck",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Review Q2 deck",
                assignee="Henry",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        # Distinct assignees → distinct rows.
        assert asyncio.run(_count_tasks(user_id)) == 2
    finally:
        asyncio.run(_cleanup(user_id))


# ── negative: completed tasks excluded from pool ─────────────────────────


@_db_required
def test_cross_thread_skips_done_tasks():
    """A prior identical-title task in progress=done state should NOT be
    reused — the user is finished with it; bringing it back to pending
    would be the supersede-on-done bug we explicitly avoid."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, _task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Refresh dashboard metrics",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
            progress_state="done",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Refresh dashboard metrics",
                assignee="Emily",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        # Done task excluded from candidate pool → new row created.
        assert asyncio.run(_count_tasks(user_id)) == 2
    finally:
        asyncio.run(_cleanup(user_id))


# ── negative: dismissed tasks excluded from pool ────────────────────────


@_db_required
def test_cross_thread_skips_dismissed_tasks():
    """A prior identical-title task in status=dismissed should NOT be
    reused — the user explicitly rejected it. Resurrecting it on a
    re-arrival would undo the dismissal. The SQL filter
    ``status != 'dismissed'`` is the gate; this test guards against a
    silent removal of that clause."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, _task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Validate cohort export",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
            status="dismissed",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Validate cohort export",
                assignee="Emily",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        # Dismissed task excluded → new row created.
        assert asyncio.run(_count_tasks(user_id)) == 2
    finally:
        asyncio.run(_cleanup(user_id))


# ── positive: VN accented assignee normalizes to a match ────────────────


@_db_required
def test_cross_thread_vietnamese_assignee_normalizes():
    """The SQL pre-filter lowercases + trims the assignee on both sides
    (``func.lower(func.coalesce(func.trim(...), ""))``). "Lê Minh Đức"
    arriving in thread B should still match a prior task seeded as
    "lê minh đức" — accent + case are NOT a barrier. This is the
    common Vietnamese-name shape and was a worry pre-implementation
    (Postgres ``lower()`` does handle Unicode case-folding for marked
    letters, but it's worth a regression test)."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Chuẩn bị bài thuyết trình IT-E6",
            assignee="lê minh đức",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Chuẩn bị bài thuyết trình IT-E6",
                # Capitalised + Đ (uppercase). Prior was lowercased "đ".
                # Match still expected after SQL lower() + trim().
                assignee="Lê Minh Đức",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        assert asyncio.run(_count_tasks(user_id)) == 1
        assert str(task_id) in out.get("saved_task_ids", [])
    finally:
        asyncio.run(_cleanup(user_id))


# ── positive: 3-thread cascade — repeated cross-thread reuse ────────────


@_db_required
def test_cross_thread_three_thread_cascade_single_row():
    """Same task surfaced across 3 distinct Gmail threads should collapse
    to ONE row. After the first cross-thread reuse the original row's
    ``dedupe_group_id`` migrates to the newest thread's group (see
    save_tasks_service group-id refresh); the third arrival then matches
    via the in-group path. Either way the count is 1, not 3."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Ship onboarding tutorial",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        # Second thread → cross-thread reuse.
        group_b = f"thread-b-{uuid.uuid4()}"
        doc_b = asyncio.run(_add_new_thread_doc(user_id, group_b))
        out_b = save_tasks_sync(
            _state(
                user_id,
                doc_b,
                title="Ship onboarding tutorial",
                assignee="Emily",
                group=group_b,
            )
        )
        assert out_b.get("errors") == [], out_b.get("errors")
        assert asyncio.run(_count_tasks(user_id)) == 1, "thread B should reuse"

        # Third thread → cross-thread reuse again (or in-group via group_b
        # refresh, both end up at count=1).
        group_c = f"thread-c-{uuid.uuid4()}"
        doc_c = asyncio.run(_add_new_thread_doc(user_id, group_c))
        out_c = save_tasks_sync(
            _state(
                user_id,
                doc_c,
                title="Ship onboarding tutorial",
                assignee="Emily",
                group=group_c,
            )
        )
        assert out_c.get("errors") == [], out_c.get("errors")
        assert asyncio.run(_count_tasks(user_id)) == 1, "thread C should reuse"
        # Original row id survives all 3 cross-thread arrivals.
        assert str(task_id) in out_c.get("saved_task_ids", [])
    finally:
        asyncio.run(_cleanup(user_id))


# ── positive: confirmed-future task IS a valid candidate ────────────────


@_db_required
def test_cross_thread_confirmed_future_task_still_eligible():
    """A confirmed task with a future deadline is still active work — the
    user hasn't done it yet, the deadline hasn't passed. A second
    mention via a different thread should fold into it rather than
    create a parallel pending row. The SQL eligibility predicate keeps
    rows where ``deadline IS NULL OR deadline >= today OR status !=
    'confirmed'`` — this test guards the future-confirmed branch."""
    from datetime import date, timedelta
    from app.services.save_tasks_service import save_tasks_sync

    future = date.today() + timedelta(days=14)
    user_id, _doc1, task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Submit DATN report draft",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
            status="confirmed",
            deadline=future,
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        out = save_tasks_sync(
            _state(
                user_id,
                doc2,
                title="Submit DATN report draft",
                assignee="Emily",
                group=new_group,
            )
        )
        assert out.get("errors") == [], out.get("errors")
        assert asyncio.run(_count_tasks(user_id)) == 1
        assert str(task_id) in out.get("saved_task_ids", [])
    finally:
        asyncio.run(_cleanup(user_id))


# ── negative: empty incoming assignee skips cross-thread entirely ───────


@_db_required
def test_cross_thread_empty_incoming_assignee_no_merge():
    """When the incoming extracted task has no assignee (or only
    whitespace), the candidate-assignee set is empty and the SQL
    pre-filter never even runs — so cross-thread dedup is skipped.
    The new row is created. This is the conservative choice: matching
    on title alone risks merging unrelated work between people."""
    from app.services.save_tasks_service import save_tasks_sync

    user_id, _doc1, _task_id = asyncio.run(
        _seed_user_and_first_task(
            title="Review API spec",
            assignee="Emily",
            group=f"thread-a-{uuid.uuid4()}",
        )
    )
    try:
        new_group = f"thread-b-{uuid.uuid4()}"
        doc2 = asyncio.run(_add_new_thread_doc(user_id, new_group))
        # State with empty-string assignee — common when an LLM can't
        # resolve a recipient from the email body alone.
        state = _state(
            user_id,
            doc2,
            title="Review API spec",
            assignee="",
            group=new_group,
        )
        out = save_tasks_sync(state)
        assert out.get("errors") == [], out.get("errors")
        # No assignee on incoming → no candidate pool → no merge attempt.
        assert asyncio.run(_count_tasks(user_id)) == 2
    finally:
        asyncio.run(_cleanup(user_id))
