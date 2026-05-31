"""End-to-end (composition) tests for the three thesis hero scenarios.

These differ from the unit suite on purpose: the unit tests prove each *piece*
in isolation (the multi-source detector as a pure function, auto-confirm against
a mocked session, the calendar-resync job handler on its own). What no unit test
proves is that the **real nodes wire together** — that a high-confidence Gmail
document flows through extract → normalize → validate → save and lands as an
auto-confirmed row, or that the validate node actually feeds the cross-source
loader's output into the multi-source detector and the conflict survives.

Scenario 2 (thread-update merge + calendar resync) needs a real database to be
meaningful, so it lives in ``backend/tests/integration/test_hero_merge_e2e.py``
where the auto-skip-when-Postgres-unreachable pattern already lives.

All tests here are quota-free: the LLM is a deterministic stub and persistence
is a capturing in-memory session. No network, no real DB, no Cerebras/Groq call.
"""
from __future__ import annotations

import uuid
from importlib import import_module
from unittest.mock import AsyncMock, MagicMock


# ── shared capturing-session plumbing (mirrors test_save_tasks_auto_confirm) ──
def _make_capturing_session() -> AsyncMock:
    """Async session mock: no reuse rows, records every session.add()."""
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


def _session_factory(session: AsyncMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ctx)


def _captured_tasks(session: MagicMock) -> list:
    from app.models.task import Task

    return [c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], Task)]


# A high-confidence single task: deadline + assignee present, confidence well
# above the 0.76 accept band → validate keeps uncertainty=None → auto-confirm.
_HIGH_CONF_TASK_JSON = (
    '[{"title":"Submit Q2 compliance report","description":"submit the signed report",'
    '"assignee":"Nguyễn Văn A",'
    '"deadline_v2":{"type":"exact","iso":"2026-06-15","start":null,"end":null,'
    '"text":"by 2026-06-15","resolved_from":"by 2026-06-15","confidence":0.93,'
    '"source":"llm","is_ambiguous":false},'
    '"priority":"high","confidence":0.93,"uncertainty":null,'
    '"evidence_quote":"submit the signed report by 2026-06-15"}]'
)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — Multi-source conflict (Gmail ↔ Drive)
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario1_multi_source_conflict_through_real_validate_node(monkeypatch) -> None:
    """A Gmail-sourced task that matches a pre-existing Drive task (same
    deliverable, same person) must surface as a ``scope="multi_source"``
    conflict — produced by the *real* validate_tasks node, not the pure helper.

    This proves the node wiring: band classification keeps the task, the
    cross-source loader's candidate is fed to the detector, and the resulting
    conflict is appended to the node's ``conflicts`` output. The loader itself
    is stubbed (its DB query is covered by its own loader test) so this stays
    offline and deterministic.
    """
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")

    gmail_doc_id = "22222222-2222-2222-2222-222222222222"
    drive_doc_id = "11111111-1111-1111-1111-111111111111"

    # The Drive task already on record — same title + same person, different
    # platform. Shaped exactly like cross_source_candidates_loader output.
    drive_candidate = {
        "id": "00000000-0000-0000-0000-000000000aaa",
        "title": "Submit Q2 compliance report",
        "source_doc_id": drive_doc_id,
        "source_type": "drive",
        "entity_canonicals": {"Nguyễn Văn A"},
    }
    monkeypatch.setattr(
        validate_mod, "load_cross_source_candidates_sync", lambda *_a, **_k: [drive_candidate]
    )
    # No LLM conflict round-trip should be needed for a single task, but stub it
    # to guarantee zero network if the intra-batch path ever reaches for it.
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", lambda *_a, **_k: '{"conflict_type":"no_conflict","description":null}'
    )

    state = {
        "user_id": str(uuid.uuid4()),
        "source_doc_id": gmail_doc_id,
        "source_type": "gmail",
        "existing_tasks": [],  # short-circuits the same-source loader
        "normalized_tasks": [
            {
                "title": "Submit Q2 compliance report",
                "assignee": "Nguyễn Văn A",
                "assignee_canonical": "Nguyễn Văn A",
                "deadline": "2026-06-15",
                "confidence": 0.93,
                "uncertainty": None,
                "evidence_quote": "submit the signed report by 2026-06-15",
                "source_ref": "batch-0",
            }
        ],
        "cleaned_text": "Please submit the signed report by 2026-06-15.",
        "errors": [],
    }

    out = validate_tasks_result = validate_mod.validate_tasks(state)

    ms = [c for c in out["conflicts"] if c.get("scope") == "multi_source"]
    assert len(ms) == 1, f"expected one multi_source conflict, got {validate_tasks_result['conflicts']}"
    c = ms[0]
    assert c["conflict_type"] == "multi_source"
    # b-ref carries the existing Drive doc id so save_tasks can persist the link.
    assert c["source_b_ref"] == drive_doc_id
    assert "drive" in c["description"] and "gmail" in c["description"]
    # The task itself was accepted (not abstained) — the conflict is surfaced
    # alongside a live task, which is what the UI needs.
    assert out["validated_tasks"][0]["abstained"] is False


def test_scenario1_no_conflict_when_only_same_platform_candidate(monkeypatch) -> None:
    """Guard: an existing *Gmail* candidate (same platform as the new task) must
    NOT produce a multi_source conflict — multi_source is cross-platform only.
    Confirms the E2E asserts real discrimination, not a rubber stamp."""
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")

    same_platform_candidate = {
        "id": "00000000-0000-0000-0000-000000000bbb",
        "title": "Submit Q2 compliance report",
        "source_doc_id": "33333333-3333-3333-3333-333333333333",
        "source_type": "gmail",  # same platform as the new task
        "entity_canonicals": {"Nguyễn Văn A"},
    }
    monkeypatch.setattr(
        validate_mod, "load_cross_source_candidates_sync", lambda *_a, **_k: [same_platform_candidate]
    )
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", lambda *_a, **_k: '{"conflict_type":"no_conflict","description":null}'
    )

    state = {
        "user_id": str(uuid.uuid4()),
        "source_doc_id": "22222222-2222-2222-2222-222222222222",
        "source_type": "gmail",
        "existing_tasks": [],
        "normalized_tasks": [
            {
                "title": "Submit Q2 compliance report",
                "assignee": "Nguyễn Văn A",
                "assignee_canonical": "Nguyễn Văn A",
                "deadline": "2026-06-15",
                "confidence": 0.93,
                "uncertainty": None,
                "source_ref": "batch-0",
            }
        ],
        "cleaned_text": "Please submit the report.",
        "errors": [],
    }

    out = validate_mod.validate_tasks(state)
    assert [c for c in out["conflicts"] if c.get("scope") == "multi_source"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — Smart auto-confirm through the full pipeline
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario3_high_confidence_doc_auto_confirms_through_full_pipeline(monkeypatch) -> None:
    """A high-confidence Gmail document, driven through the REAL
    extract → normalize → validate → save chain, must be persisted as an
    auto-confirmed task (``status="confirmed"``, ``confirmed_by="system"``).

    Only the two ends are stubbed — the LLM (deterministic, quota-free) and the
    database session (capturing, offline). Everything between is the production
    code path, so this catches a regression in any node that would strip the
    high-confidence signal before save (e.g. validate wrongly banding it
    uncertain, or normalize dropping the deadline).
    """
    from app.pipeline.graph import pipeline

    extract_mod = import_module("app.pipeline.nodes.extract_tasks")
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")
    save_service = import_module("app.services.save_tasks_service")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")

    monkeypatch.setattr(extract_mod, "call_llm", lambda *_a, **_k: _HIGH_CONF_TASK_JSON)
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", lambda *_a, **_k: '{"conflict_type":"no_conflict","description":null}'
    )
    # No cross-source / same-source candidates → no conflict gate on auto-confirm.
    monkeypatch.setattr(validate_mod, "load_cross_source_candidates_sync", lambda *_a, **_k: [])

    session = _make_capturing_session()
    monkeypatch.setattr(save_service, "AsyncSessionLocal", _session_factory(session))

    # Capture what dispatch receives instead of making real MCP calendar calls.
    dispatched: dict = {}

    def _capture_dispatch(state):
        dispatched["saved_task_ids"] = list(state.get("saved_task_ids", []))
        return {"notifications_sent": [], "errors": []}

    monkeypatch.setattr(dispatch_mod, "dispatch_notifications_sync", _capture_dispatch)

    result = pipeline.invoke(
        {
            "user_id": str(uuid.uuid4()),
            "access_token": "tok",
            "source_doc_id": str(uuid.uuid4()),
            "source_type": "gmail",
            "raw_content": "<p>Please submit the signed report by 2026-06-15.</p>",
            "metadata": {"sender": "boss@example.com", "sent_at": "2026-05-21T10:00:00Z"},
            "existing_tasks": [],
            "errors": [],
            "should_stop": False,
        }
    )

    assert result.get("should_stop") is False
    # Validate kept the task in the accept band (uncertainty stays None).
    vt = result["validated_tasks"]
    assert len(vt) == 1 and vt[0]["abstained"] is False
    assert vt[0].get("uncertainty") is None

    # Save auto-confirmed it: this is the cross-node payoff.
    tasks = _captured_tasks(session)
    assert len(tasks) == 1, "expected exactly one persisted task"
    assert tasks[0].status == "confirmed"
    assert tasks[0].confirmed_by == "system"

    # The save → dispatch handoff still occurred (dispatch gating itself is
    # unit-covered in test_notification_confirm_gate / dispatch node tests).
    assert "saved_task_ids" in dispatched


def test_scenario3_uncertain_doc_stays_pending_through_full_pipeline(monkeypatch) -> None:
    """Mirror guard: a below-threshold-confidence document must NOT auto-confirm
    when run through the same full pipeline — proves the auto-confirm is
    genuinely gated on the upstream confidence signal, not unconditional."""
    from app.pipeline.graph import pipeline

    extract_mod = import_module("app.pipeline.nodes.extract_tasks")
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")
    save_service = import_module("app.services.save_tasks_service")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")

    # confidence 0.60 → uncertain band (0.55–0.76) → validate stamps uncertainty.
    low_conf_json = (
        '[{"title":"Maybe follow up with vendor","description":"unclear ask",'
        '"assignee":"Nguyễn Văn A",'
        '"deadline_v2":{"type":"exact","iso":"2026-06-15","start":null,"end":null,'
        '"text":"sometime","resolved_from":"sometime","confidence":0.60,'
        '"source":"llm","is_ambiguous":true},'
        '"priority":"medium","confidence":0.60,"uncertainty":null}]'
    )
    monkeypatch.setattr(extract_mod, "call_llm", lambda *_a, **_k: low_conf_json)
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", lambda *_a, **_k: '{"conflict_type":"no_conflict","description":null}'
    )
    monkeypatch.setattr(validate_mod, "load_cross_source_candidates_sync", lambda *_a, **_k: [])

    session = _make_capturing_session()
    monkeypatch.setattr(save_service, "AsyncSessionLocal", _session_factory(session))
    monkeypatch.setattr(
        dispatch_mod, "dispatch_notifications_sync",
        lambda _state: {"notifications_sent": [], "errors": []},
    )

    pipeline.invoke(
        {
            "user_id": str(uuid.uuid4()),
            "access_token": "tok",
            "source_doc_id": str(uuid.uuid4()),
            "source_type": "gmail",
            "raw_content": "<p>Maybe follow up with the vendor sometime.</p>",
            "metadata": {"sender": "x@example.com", "sent_at": "2026-05-21T10:00:00Z"},
            "existing_tasks": [],
            "errors": [],
            "should_stop": False,
        }
    )

    tasks = _captured_tasks(session)
    assert len(tasks) == 1
    assert tasks[0].status == "pending"
    assert tasks[0].confirmed_by is None
