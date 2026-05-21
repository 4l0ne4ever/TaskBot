"""Unit tests for Phase 7.2 auto-confirm in save_tasks_service.

Auto-confirm criteria (all must pass for a NEW task):
  1. uncertainty IS NULL — pipeline's calibrated band accepted the task
  2. title NOT in intra-batch conflict titles — conflicted tasks need human review
  3. deadline IS NOT NULL OR assignee IS NOT NULL — task is actionable

Auto-confirm NEVER fires on the reuse (update-in-place) path — prevents
the confirmed→pending reset (7.3b) → auto-confirm → confirmed loop.

Tests use a mocked session factory to stay fast and offline.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch


def _make_vt(
    *,
    title: str,
    assignee: str | None = "Nguyễn Văn A",
    deadline: str | None = "2026-06-01",
    uncertainty: dict | None = None,
    abstained: bool = False,
) -> dict:
    return {
        "title": title,
        "assignee": assignee,
        "deadline": deadline,
        "uncertainty": uncertainty,
        "decision_band": "abstain" if abstained else "accept",
        "abstained": abstained,
        "missing_fields": [],
        "source_ref": "email-1",
    }


def _make_state(
    *,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    validated_tasks: list[dict],
    conflicts: list[dict] | None = None,
) -> dict:
    return {
        "user_id": str(user_id),
        "source_doc_id": str(doc_id),
        "validated_tasks": validated_tasks,
        "conflicts": conflicts or [],
        "errors": [],
        "metadata": {"sent_at": "2026-05-21"},
    }


def _captured_tasks(fake_session: MagicMock) -> list[MagicMock]:
    """Return Task objects passed to session.add()."""
    from app.models.task import Task
    return [
        call.args[0]
        for call in fake_session.add.call_args_list
        if isinstance(call.args[0], Task)
    ]


def _run_save(state: dict) -> dict:
    import asyncio
    from app.services.save_tasks_service import async_save_tasks
    return asyncio.run(async_save_tasks(state))


def _build_session_factory(session_mock: AsyncMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return factory


def _make_session() -> AsyncMock:
    # Minimal async session mock: execute returns empty (no reuse rows),
    # flush/begin are no-ops, add records calls.
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    execute_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=None)

    begin_ctx = MagicMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=session)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    return session


# ── create-path auto-confirm tests ────────────────────────────────────────────


def test_high_confidence_task_is_auto_confirmed(monkeypatch) -> None:
    """uncertainty=None + no conflict + has deadline → status=confirmed, confirmed_by=system."""
    user_id, doc_id = uuid.uuid4(), uuid.uuid4()
    session = _make_session()
    monkeypatch.setattr("app.services.save_tasks_service.AsyncSessionLocal", _build_session_factory(session))

    state = _make_state(
        user_id=user_id,
        doc_id=doc_id,
        validated_tasks=[_make_vt(title="Finalize contract", deadline="2026-06-15", uncertainty=None)],
    )
    _run_save(state)

    tasks = _captured_tasks(session)
    assert len(tasks) == 1
    assert tasks[0].status == "confirmed"
    assert tasks[0].confirmed_by == "system"


def test_uncertain_task_stays_pending(monkeypatch) -> None:
    """uncertainty dict present → auto-confirm must NOT fire, task stays pending."""
    user_id, doc_id = uuid.uuid4(), uuid.uuid4()
    session = _make_session()
    monkeypatch.setattr("app.services.save_tasks_service.AsyncSessionLocal", _build_session_factory(session))

    state = _make_state(
        user_id=user_id,
        doc_id=doc_id,
        validated_tasks=[_make_vt(
            title="Ambiguous task",
            uncertainty={"type": "ambiguous", "reason": "deadline unclear"},
        )],
    )
    _run_save(state)

    tasks = _captured_tasks(session)
    assert tasks[0].status == "pending"
    assert tasks[0].confirmed_by is None


def test_conflicted_task_stays_pending(monkeypatch) -> None:
    """Task whose title appears in an intra-batch conflict → human review needed, no auto-confirm."""
    user_id, doc_id = uuid.uuid4(), uuid.uuid4()
    session = _make_session()
    monkeypatch.setattr("app.services.save_tasks_service.AsyncSessionLocal", _build_session_factory(session))

    conflicts = [
        {
            "conflict_type": "deadline_conflict",
            "task_title": "Submit NDA",
            "description": "Different deadlines",
            "source_a_ref": "email-1",
        }
    ]
    state = _make_state(
        user_id=user_id,
        doc_id=doc_id,
        validated_tasks=[_make_vt(title="Submit NDA", deadline="2026-06-01", uncertainty=None)],
        conflicts=conflicts,
    )
    _run_save(state)

    tasks = _captured_tasks(session)
    assert tasks[0].status == "pending"
    assert tasks[0].confirmed_by is None


def test_no_deadline_and_no_assignee_stays_pending(monkeypatch) -> None:
    """High-confidence task with neither deadline nor assignee is not actionable — no auto-confirm."""
    user_id, doc_id = uuid.uuid4(), uuid.uuid4()
    session = _make_session()
    monkeypatch.setattr("app.services.save_tasks_service.AsyncSessionLocal", _build_session_factory(session))

    state = _make_state(
        user_id=user_id,
        doc_id=doc_id,
        validated_tasks=[_make_vt(title="FYI: office closed", deadline=None, assignee=None, uncertainty=None)],
    )
    _run_save(state)

    tasks = _captured_tasks(session)
    assert tasks[0].status == "pending"
    assert tasks[0].confirmed_by is None


def test_high_confidence_with_assignee_only_is_auto_confirmed(monkeypatch) -> None:
    """deadline=None but assignee set → still actionable, auto-confirm fires."""
    user_id, doc_id = uuid.uuid4(), uuid.uuid4()
    session = _make_session()
    monkeypatch.setattr("app.services.save_tasks_service.AsyncSessionLocal", _build_session_factory(session))

    state = _make_state(
        user_id=user_id,
        doc_id=doc_id,
        validated_tasks=[_make_vt(title="Review draft", deadline=None, assignee="Lê Hương", uncertainty=None)],
    )
    _run_save(state)

    tasks = _captured_tasks(session)
    assert tasks[0].status == "confirmed"
    assert tasks[0].confirmed_by == "system"
