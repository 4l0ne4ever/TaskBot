from importlib import import_module

from app.pipeline.nodes.validate_tasks import validate_tasks


def test_validate_tasks_adds_missing_fields() -> None:
    result = validate_tasks(
        {
            "normalized_tasks": [
                {"title": "Submit report", "assignee": None, "deadline": None, "priority": "high"}
            ],
            "errors": [],
            "existing_tasks": [],
        }
    )
    assert result["validated_tasks"][0]["missing_fields"] == ["deadline", "assignee"]
    assert result["validated_tasks"][0]["decision_band"] == "abstain"
    assert result["validated_tasks"][0]["abstained"] is True
    assert result["conflicts"] == []


def test_validate_tasks_detects_conflict_with_similar_existing(monkeypatch) -> None:
    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(
        import_module("app.pipeline.nodes.conflict_detectors"),
        "call_llm",
        lambda *_args, **_kwargs: '{"conflict_type":"deadline_conflict","description":"Different deadlines"}',
    )

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit Q1 report",
                    "assignee": "Bob",
                    "deadline": "2026-04-05",
                    "source_ref": "new-1",
                    "confidence": 0.9,
                }
            ],
            "existing_tasks": [
                {"id": "old-1", "title": "Submit Q1 report", "assignee": "Bob", "deadline": "2026-04-03"}
            ],
            "errors": [],
        }
    )
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "deadline_conflict"


def test_validate_tasks_ignores_invalid_conflict_response(monkeypatch) -> None:
    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", lambda *_args, **_kwargs: "invalid-json")

    result = validate_tasks(
        {
            "normalized_tasks": [{"title": "Prepare slides", "assignee": "Ann", "deadline": "2026-04-10"}],
            "existing_tasks": [{"id": "old-2", "title": "Prepare slides", "assignee": "Ben", "deadline": "2026-04-10"}],
            "errors": [],
        }
    )
    assert result["conflicts"] == []
    assert result["validated_tasks"][0]["decision_band"] == "abstain"


def test_validate_tasks_abstains_when_evidence_quote_not_in_source() -> None:
    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Bob",
                    "deadline": "2026-04-10",
                    "confidence": 0.95,
                    "evidence_quote": "fabricated substring",
                }
            ],
            "cleaned_text": "Please Submit report by Monday for the board.",
            "existing_tasks": [],
            "errors": [],
        }
    )
    vt = result["validated_tasks"][0]
    assert vt["abstained"] is True
    assert vt["decision_band"] == "abstain"
    assert "evidence_quote not found" in (vt.get("uncertainty") or {}).get("reason", "")


def test_validate_tasks_accepts_when_evidence_quote_in_source() -> None:
    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Bob",
                    "deadline": "2026-04-10",
                    "confidence": 0.95,
                    "evidence_quote": "Submit report by Monday",
                }
            ],
            "cleaned_text": "Please Submit report by Monday for the board.",
            "existing_tasks": [],
            "errors": [],
        }
    )
    vt = result["validated_tasks"][0]
    assert vt["abstained"] is False
    assert vt["decision_band"] == "accept"


def test_validate_tasks_accepts_evidence_quote_with_whitespace_and_case_variation() -> None:
    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Bob",
                    "deadline": "2026-04-10",
                    "confidence": 0.95,
                    "evidence_quote": "submit the q1 report by monday",
                }
            ],
            "cleaned_text": "Please SUBMIT   the Q1\nreport by\tMonday for the board.",
            "existing_tasks": [],
            "errors": [],
        }
    )
    vt = result["validated_tasks"][0]
    assert vt["abstained"] is False
    assert vt["decision_band"] == "accept"


def test_validate_tasks_marks_uncertain_band() -> None:
    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Prepare deck",
                    "assignee": "Ann",
                    "deadline": "2026-04-10",
                    "priority": "medium",
                    "confidence": 0.7,
                }
            ],
            "existing_tasks": [],
            "errors": [],
        }
    )
    item = result["validated_tasks"][0]
    assert item["decision_band"] == "uncertain"
    assert item["abstained"] is False
    assert item["uncertainty"]["type"] == "ambiguous"


def test_validate_tasks_marks_abstain_and_skips_conflict_call(monkeypatch) -> None:
    module = import_module("app.pipeline.nodes.validate_tasks")
    calls = {"count": 0}

    def _fake_call_llm(*_args, **_kwargs):
        calls["count"] += 1
        return '{"conflict_type":"deadline_conflict","description":"Different deadlines"}'

    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", _fake_call_llm)
    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit Q1 report",
                    "assignee": "Bob",
                    "deadline": "2026-04-05",
                    "confidence": 0.5,
                }
            ],
            "existing_tasks": [{"id": "old-1", "title": "Submit Q1 report", "assignee": "Bob", "deadline": "2026-04-03"}],
            "errors": [],
        }
    )
    item = result["validated_tasks"][0]
    assert item["decision_band"] == "abstain"
    assert item["abstained"] is True
    assert item["uncertainty"]["type"] == "missing"
    assert result["conflicts"] == []
    assert calls["count"] == 0


def test_validate_tasks_detects_intra_batch_reassignment(monkeypatch) -> None:
    """ac-157 family: two tasks in the same batch with the same title but
    different assignees — later revision wins, earlier is marked
    ``superseded_by`` and an assignee_conflict is recorded."""
    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(
        import_module("app.pipeline.nodes.conflict_detectors"),
        "call_llm",
        lambda *_args, **_kwargs: '{"conflict_type":"assignee_conflict","description":"reassigned"}',
    )

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Wireframe trang chủ",
                    "assignee": "Đỗ Văn Hải",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                    "source_ref": "email-1",
                },
                {
                    "title": "Wireframe trang chủ",
                    "assignee": "Lê Minh Đức",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                    "source_ref": "email-2",
                },
            ],
            "existing_tasks": [],
            "errors": [],
        }
    )

    tasks = result["validated_tasks"]
    assert tasks[0]["superseded_by"] == "email-2"
    assert tasks[0]["abstained"] is True
    assert tasks[0]["uncertainty"]["type"] == "superseded"
    assert "superseded_by" not in tasks[1]
    assert tasks[1]["abstained"] is False
    intra = [c for c in result["conflicts"] if c.get("scope") == "intra_batch"]
    assert len(intra) == 1
    assert intra[0]["conflict_type"] == "assignee_conflict"
    assert intra[0]["source_a_ref"] == "email-1"
    assert intra[0]["source_b_ref"] == "email-2"


def test_validate_tasks_intra_batch_skips_dissimilar_titles(monkeypatch) -> None:
    """When no pair of tasks is similar enough to share a deliverable,
    the intra-batch pass must not invoke the LLM at all — similarity
    is the scoping filter that keeps the extra cost bounded."""
    module = import_module("app.pipeline.nodes.validate_tasks")
    calls = {"count": 0}

    def _fake_call_llm(*_args, **_kwargs):
        calls["count"] += 1
        return '{"conflict_type":"assignee_conflict","description":"x"}'

    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", _fake_call_llm)

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Write spec document",
                    "assignee": "Ann",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                },
                {
                    "title": "Ship frontend v3 release",
                    "assignee": "Bob",
                    "deadline": "2026-04-12",
                    "confidence": 0.9,
                },
            ],
            "existing_tasks": [],
            "errors": [],
        }
    )
    assert calls["count"] == 0
    assert result["conflicts"] == []
    assert all("superseded_by" not in t for t in result["validated_tasks"])


def test_validate_tasks_intra_batch_no_conflict_keeps_both(monkeypatch) -> None:
    """Similar titles but LLM classifies as ``no_conflict`` — both tasks
    must remain active, no conflict record emitted."""
    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(
        import_module("app.pipeline.nodes.conflict_detectors"),
        "call_llm",
        lambda *_args, **_kwargs: '{"conflict_type":"no_conflict","description":null}',
    )

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Review PR",
                    "assignee": "Ann",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                },
                {
                    "title": "Review PR",
                    "assignee": "Ben",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                },
            ],
            "existing_tasks": [],
            "errors": [],
        }
    )
    assert all("superseded_by" not in t for t in result["validated_tasks"])
    assert [c for c in result["conflicts"] if c.get("scope") == "intra_batch"] == []


def test_validate_tasks_intra_batch_respects_budget(monkeypatch) -> None:
    """``max_conflict_checks_per_task`` is a hard ceiling shared across
    the inter-doc and intra-batch passes so a pathological input cannot
    explode LLM cost."""
    module = import_module("app.pipeline.nodes.validate_tasks")
    calls = {"count": 0}

    def _fake_call_llm(*_args, **_kwargs):
        calls["count"] += 1
        return '{"conflict_type":"assignee_conflict","description":"x"}'

    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", _fake_call_llm)

    from app.pipeline import policy as policy_mod

    base_policy = policy_mod.get_pipeline_policy()
    capped = base_policy.__class__(
        version=base_policy.version,
        confidence_abstain_threshold=base_policy.confidence_abstain_threshold,
        confidence_uncertain_threshold=base_policy.confidence_uncertain_threshold,
        conflict_title_similarity_threshold=0.5,
        multi_source_title_similarity_threshold=base_policy.multi_source_title_similarity_threshold,
        multi_source_conflict_lookback_days=base_policy.multi_source_conflict_lookback_days,
        max_conflict_checks_per_task=1,
        extraction_guidance=base_policy.extraction_guidance,
        validate_evidence_in_source=base_policy.validate_evidence_in_source,
    )
    monkeypatch.setattr(module, "get_pipeline_policy", lambda: capped)

    result = validate_tasks(
        {
            "normalized_tasks": [
                {"title": "Review PR", "assignee": "A", "deadline": "2026-04-10", "confidence": 0.9, "source_ref": "r1"},
                {"title": "Review PR", "assignee": "B", "deadline": "2026-04-10", "confidence": 0.9, "source_ref": "r2"},
                {"title": "Review PR", "assignee": "C", "deadline": "2026-04-10", "confidence": 0.9, "source_ref": "r3"},
            ],
            "existing_tasks": [],
            "errors": [],
        }
    )
    assert calls["count"] == 1
    intra = [c for c in result["conflicts"] if c.get("scope") == "intra_batch"]
    assert len(intra) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2.1 — thread-update scope tagging
# ─────────────────────────────────────────────────────────────────────────────
#
# When the source text carries a structural thread-update marker (e.g.
# "Update:", "Cập nhật:", "Đã đổi:"), an intra-batch conflict is promoted
# from ``scope="intra_batch"`` to ``scope="thread_update"`` so the UI can
# render the timeline accurately. Resolution semantics (last-writer-wins via
# source_ref order) are unchanged.


def _intra_batch_reassignment_state(source_text: str | None) -> dict:
    """Shared scenario fixture: two tasks for the same deliverable with
    different assignees, parameterised on the surrounding source text."""
    return {
        "normalized_tasks": [
            {
                "title": "Wireframe trang chủ",
                "assignee": "Đỗ Văn Hải",
                "deadline": "2026-04-10",
                "confidence": 0.9,
                "source_ref": "email-1",
            },
            {
                "title": "Wireframe trang chủ",
                "assignee": "Lê Minh Đức",
                "deadline": "2026-04-10",
                "confidence": 0.9,
                "source_ref": "email-2",
            },
        ],
        "existing_tasks": [],
        "errors": [],
        "cleaned_text": source_text or "",
    }


def _stub_conflict_llm(monkeypatch, conflict_type: str = "assignee_conflict") -> None:
    """Make every ``call_llm`` invocation return a fixed conflict classification."""
    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(
        import_module("app.pipeline.nodes.conflict_detectors"),
        "call_llm",
        lambda *_a, **_k: f'{{"conflict_type":"{conflict_type}","description":"reassigned"}}',
    )


def test_thread_update_scope_when_vietnamese_marker_present(monkeypatch) -> None:
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải."
    )
    result = validate_tasks(state)
    scopes = [c.get("scope") for c in result["conflicts"]]
    assert "thread_update" in scopes
    assert "intra_batch" not in scopes


def test_thread_update_scope_when_english_update_marker_present(monkeypatch) -> None:
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "Update: the wireframe is now handled by Lê Minh Đức."
    )
    result = validate_tasks(state)
    assert any(c.get("scope") == "thread_update" for c in result["conflicts"])


def test_thread_update_scope_for_cap_nhat_marker(monkeypatch) -> None:
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "Cập nhật: deadline mới sớm hơn."
    )
    result = validate_tasks(state)
    assert any(c.get("scope") == "thread_update" for c in result["conflicts"])


def test_thread_update_scope_for_now_predicate(monkeypatch) -> None:
    """No ``Update:`` prefix but the source uses the 'now (due|assigned|
    handled)' predicate form — still a thread-update signal."""
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "the wireframe is now assigned to Lê Minh Đức."
    )
    result = validate_tasks(state)
    assert any(c.get("scope") == "thread_update" for c in result["conflicts"])


def test_thread_update_scope_for_thay_vi(monkeypatch) -> None:
    """Vietnamese reassignment phrase ``thay vì`` / ``thay cho``."""
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "Lê Minh Đức phụ trách thay vì Đỗ Văn Hải."
    )
    result = validate_tasks(state)
    assert any(c.get("scope") == "thread_update" for c in result["conflicts"])


def test_intra_batch_scope_when_no_thread_marker(monkeypatch) -> None:
    """Two same-deliverable tasks in a source without any thread marker
    must keep the original ``intra_batch`` scope. Guards against false
    promotion when the conflict is just an LLM duplicate, not a thread."""
    _stub_conflict_llm(monkeypatch)
    state = _intra_batch_reassignment_state(
        "Two reminders went out for the same wireframe task today."
    )
    result = validate_tasks(state)
    scopes = [c.get("scope") for c in result["conflicts"]]
    assert scopes == ["intra_batch"]


def test_thread_marker_without_title_similarity_emits_no_conflict(monkeypatch) -> None:
    """Marker presence alone is not enough — the pair must still cross the
    title-similarity threshold. Otherwise the thread-update scope would
    fire on unrelated tasks that happen to share a thread."""
    calls = {"count": 0}

    def _fake(*_a, **_k):
        calls["count"] += 1
        return '{"conflict_type":"assignee_conflict","description":"x"}'

    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", _fake)

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Write spec document",
                    "assignee": "Ann",
                    "deadline": "2026-04-10",
                    "confidence": 0.9,
                    "source_ref": "email-1",
                },
                {
                    "title": "Ship release notes",
                    "assignee": "Bob",
                    "deadline": "2026-04-12",
                    "confidence": 0.9,
                    "source_ref": "email-2",
                },
            ],
            "existing_tasks": [],
            "errors": [],
            "cleaned_text": "Update: schedule changed for both items.",
        }
    )
    assert calls["count"] == 0
    intra = [c for c in result["conflicts"] if c.get("scope") in ("intra_batch", "thread_update")]
    assert intra == []


# ─────────────────────────────────────────────────────────────────────────────
# Phase A' — inter-doc scope tagging (cross-document follow-ups)
# ─────────────────────────────────────────────────────────────────────────────
# Real user journey: a follow-up email arrives days after the original task
# was extracted and persisted. The inter-document loop classifies the new
# task against existing DB rows; when the new task's source text carries a
# thread-update marker, the resulting conflict is promoted from plain
# ``inter_doc`` to ``thread_update`` so the UI can render it as a timeline.


def _inter_doc_followup_state(source_text: str | None) -> dict:
    """One new task that conflicts with one existing persisted task on the
    same deliverable, parameterised on the surrounding source text."""
    return {
        "normalized_tasks": [
            {
                "title": "Submit Q1 report",
                "assignee": "Lê Minh Đức",
                "deadline": "2026-04-12",
                "confidence": 0.9,
                "source_ref": "email-2",
            }
        ],
        "existing_tasks": [
            {
                "id": "00000000-0000-0000-0000-0000000000aa",
                "title": "Submit Q1 report",
                "assignee": "Đỗ Văn Hải",
                "deadline": "2026-04-10",
                "source_ref": "email-1",
            }
        ],
        "errors": [],
        "cleaned_text": source_text or "",
    }


def test_inter_doc_scope_thread_update_when_marker_present(monkeypatch) -> None:
    _stub_conflict_llm(monkeypatch, conflict_type="assignee_conflict")
    state = _inter_doc_followup_state(
        "Update: Lê Minh Đức will own the Q1 report submission going forward."
    )
    result = validate_tasks(state)
    scopes = [c.get("scope") for c in result["conflicts"]]
    assert scopes == ["thread_update"]


def test_inter_doc_scope_plain_inter_doc_when_no_marker(monkeypatch) -> None:
    """No marker in the new email's source text → conflict is still emitted
    (the LLM said so), but scope stays plain ``inter_doc`` rather than being
    promoted to ``thread_update``. Guards against false promotion."""
    _stub_conflict_llm(monkeypatch, conflict_type="assignee_conflict")
    state = _inter_doc_followup_state(
        "Please confirm the Q1 report owner — Lê Minh Đức says he's handling it."
    )
    result = validate_tasks(state)
    scopes = [c.get("scope") for c in result["conflicts"]]
    assert scopes == ["inter_doc"]


def test_inter_doc_marker_does_not_invent_conflict_without_title_match(monkeypatch) -> None:
    """Marker presence must not promote unrelated existing tasks into the
    conflict set — title similarity is still the gate. Verifies the
    candidate-filter (above ``conflict_title_similarity_threshold``) runs
    before the scope-tagging in ``_build_conflicts_for_task``."""
    calls = {"count": 0}

    def _fake(*_a, **_k):
        calls["count"] += 1
        return '{"conflict_type":"assignee_conflict","description":"x"}'

    module = import_module("app.pipeline.nodes.validate_tasks")
    monkeypatch.setattr(import_module("app.pipeline.nodes.conflict_detectors"), "call_llm", _fake)

    result = validate_tasks(
        {
            "normalized_tasks": [
                {
                    "title": "Submit Q1 report",
                    "assignee": "Lê Minh Đức",
                    "deadline": "2026-04-12",
                    "confidence": 0.9,
                    "source_ref": "email-2",
                }
            ],
            "existing_tasks": [
                {
                    "id": "00000000-0000-0000-0000-0000000000bb",
                    "title": "Plan summer offsite",  # unrelated
                    "assignee": "Đỗ Văn Hải",
                    "deadline": "2026-07-01",
                }
            ],
            "errors": [],
            "cleaned_text": "Update: Lê Minh Đức will own the Q1 report.",
        }
    )
    assert calls["count"] == 0
    assert result["conflicts"] == []


def test_has_thread_update_marker_pure_helper() -> None:
    """Cheap pure-function checks that lock the patterns in place — adding
    a new marker should require adding a test here too so the contract
    stays explicit."""
    from app.pipeline.nodes.validate_tasks import _has_thread_update_marker

    assert _has_thread_update_marker("Update: schedule changed") is True
    assert _has_thread_update_marker("UPDATED: see latest") is True
    assert _has_thread_update_marker("Cập nhật: deadline mới") is True
    assert _has_thread_update_marker("Đã đổi: người phụ trách") is True
    assert _has_thread_update_marker("Revised plan attached") is True
    assert _has_thread_update_marker("Sửa lại theo feedback") is True
    assert _has_thread_update_marker("now due tomorrow") is True
    assert _has_thread_update_marker("Reassigned to Mary") is True
    assert _has_thread_update_marker("Lê thay vì Đỗ") is True

    # Negatives: words appearing in non-thread-update context must NOT match.
    assert _has_thread_update_marker("FYI — release notes attached") is False
    assert _has_thread_update_marker("Please review before Friday") is False
    assert _has_thread_update_marker("") is False
    assert _has_thread_update_marker(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2.2 — multi-source conflict detection (pure-function detector)
# ─────────────────────────────────────────────────────────────────────────────
#
# The detector is tested in isolation so we don't need a database for the
# logic checks; the loader is a thin DB query covered by its own integration
# test below. ``_detect_multi_source_conflicts`` takes a candidate list
# already shaped like loader output and returns conflict records.


def _stub_policy_for_ms(monkeypatch, ms_threshold: float = 0.85, lookback: int = 30):
    """Return a real-ish policy stub with multi-source thresholds set."""
    from app.pipeline import policy as policy_mod

    base = policy_mod.get_pipeline_policy()
    capped = base.__class__(
        version=base.version,
        confidence_abstain_threshold=base.confidence_abstain_threshold,
        confidence_uncertain_threshold=base.confidence_uncertain_threshold,
        conflict_title_similarity_threshold=base.conflict_title_similarity_threshold,
        multi_source_title_similarity_threshold=ms_threshold,
        multi_source_conflict_lookback_days=lookback,
        max_conflict_checks_per_task=base.max_conflict_checks_per_task,
        extraction_guidance=base.extraction_guidance,
        validate_evidence_in_source=base.validate_evidence_in_source,
    )
    return capped


def _new_tasks(*specs):
    """Helper: turn ``(idx, dict)`` tuples into the list shape the detector
    expects."""
    return list(specs)


def test_multi_source_detector_emits_conflict_on_gmail_drive_match() -> None:
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "drive",
            "entity_canonicals": {"Hương"},
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert len(out) == 1
    c = out[0]
    assert c["scope"] == "multi_source"
    assert c["conflict_type"] == "multi_source"
    assert c["source_b_ref"] == "11111111-1111-1111-1111-111111111111"
    assert "drive" in c["description"] and "gmail" in c["description"]
    # Bug 2026-06-08: multi_source emit must carry the existing task UUID in
    # task_id_b so save_tasks_service can populate conflicts.task_ids[2] with
    # a real task id (not a source_doc id, which produced phantom UI cards
    # showing "Source content not available for this reference").
    assert c["task_id_b"] == "00000000-0000-0000-0000-000000000aaa"


def test_multi_source_skipped_when_same_source_type() -> None:
    """Two Gmail tasks → not multi-source (intra-batch / inter-doc-same-type
    is the responsibility of other detectors)."""
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "gmail",  # same as new
            "entity_canonicals": {"Hương"},
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert out == []


def test_multi_source_skipped_when_below_title_threshold() -> None:
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Plan vacation",  # very different title
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "drive",
            "entity_canonicals": {"Hương"},
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert out == []


def test_multi_source_requires_entity_overlap_when_both_have_entities() -> None:
    """Title matches + cross-source but person-entity sets disjoint → no
    conflict (the title coincidence is probably just topical noise)."""
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "drive",
            "entity_canonicals": {"Minh"},  # disjoint from new
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert out == []


def test_multi_source_fallback_when_new_task_has_no_assignee() -> None:
    """``assignee_canonical=None`` means the new task contributes an empty
    entity set — by design we fall back to title + cross-source filters
    rather than penalise the task."""
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": None, "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "drive",
            "entity_canonicals": {"Hương"},
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert len(out) == 1


def test_multi_source_fallback_when_candidate_has_no_entities() -> None:
    """Mirror case: candidate has empty entity set → still detect."""
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": "11111111-1111-1111-1111-111111111111",
            "source_type": "drive",
            "entity_canonicals": set(),  # empty
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id="22222222-2222-2222-2222-222222222222",
        new_source_type="gmail",
    )
    assert len(out) == 1


def test_multi_source_skipped_when_same_source_doc_id() -> None:
    """Defensive: if a candidate accidentally has the same source_doc_id as
    the new run (loader should already exclude this, but the detector must
    not double-emit)."""
    from app.pipeline.nodes.validate_tasks import _detect_multi_source_conflicts

    new_task = {"title": "Submit Q1 report", "assignee_canonical": "Hương", "source_ref": "batch-0"}
    same_doc = "22222222-2222-2222-2222-222222222222"
    candidates = [
        {
            "id": "00000000-0000-0000-0000-000000000aaa",
            "title": "Submit Q1 report",
            "source_doc_id": same_doc,
            "source_type": "drive",
            "entity_canonicals": {"Hương"},
        }
    ]
    policy = _make_policy_stub(ms_threshold=0.85)
    out = _detect_multi_source_conflicts(
        _new_tasks((0, new_task)),
        candidates,
        policy,
        new_source_doc_id=same_doc,
        new_source_type="gmail",
    )
    assert out == []


def test_entity_overlap_compatible_helper() -> None:
    """Locks the hybrid overlap rule contract."""
    from app.pipeline.nodes.validate_tasks import _entity_overlap_compatible

    # Both sides empty → True (fallback)
    assert _entity_overlap_compatible(set(), set()) is True
    # One empty → True (fallback)
    assert _entity_overlap_compatible({"Hương"}, set()) is True
    assert _entity_overlap_compatible(set(), {"Hương"}) is True
    # Both non-empty, overlap → True
    assert _entity_overlap_compatible({"Hương"}, {"Hương", "Minh"}) is True
    # Both non-empty, disjoint → False
    assert _entity_overlap_compatible({"Hương"}, {"Minh"}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Cross-detector dedup (2026-06-08 forensic)
# ─────────────────────────────────────────────────────────────────────────────


def test_dedup_collapses_same_pair_multi_source_and_thread_update_to_one() -> None:
    """The 2026-06-08 bug: an upload vs an existing gmail task fired both
    multi_source (different source types) and thread_update (different
    deadlines), giving the user two cards for one conflict. The dedup pass
    must keep the more specific scope (thread_update) and drop multi_source."""
    from app.pipeline.nodes.validate_tasks import _dedup_conflicts_by_pair

    existing_task_uuid = "ee4b01d3-d27f-46c5-8abc-82be1f70a9c0"
    conflicts = [
        {
            "scope": "multi_source",
            "conflict_type": "multi_source",
            "task_title": "write release notes v3.0",
            "source_a_ref": "batch-0",
            "source_b_ref": "740552ca-cd41-4490-b999-827cf6c2659e",  # source_doc
            "task_id_b": existing_task_uuid,
        },
        {
            "scope": "thread_update",
            "conflict_type": "deadline_conflict",
            "task_title": "write release notes v3.0",
            "source_a_ref": "upload-0",
            "source_b_ref": existing_task_uuid,
        },
    ]
    out = _dedup_conflicts_by_pair(conflicts)
    assert len(out) == 1
    assert out[0]["scope"] == "thread_update"


def test_dedup_keeps_distinct_pairs_intact() -> None:
    """Two conflicts pointing at *different* existing tasks must both survive
    — dedup is per pair, not blanket."""
    from app.pipeline.nodes.validate_tasks import _dedup_conflicts_by_pair

    conflicts = [
        {
            "scope": "multi_source",
            "task_title": "ship release notes",
            "task_id_b": "11111111-1111-1111-1111-111111111111",
            "source_b_ref": "doc-a",
        },
        {
            "scope": "multi_source",
            "task_title": "ship release notes",
            "task_id_b": "22222222-2222-2222-2222-222222222222",
            "source_b_ref": "doc-b",
        },
    ]
    out = _dedup_conflicts_by_pair(conflicts)
    assert len(out) == 2


def test_dedup_specificity_order() -> None:
    """thread_update > inter_doc > intra_batch > multi_source — verify by
    seeding pairs in every combination and checking the winner."""
    from app.pipeline.nodes.validate_tasks import _dedup_conflicts_by_pair

    cases = [
        (["multi_source", "intra_batch"], "intra_batch"),
        (["multi_source", "inter_doc"], "inter_doc"),
        (["multi_source", "thread_update"], "thread_update"),
        (["intra_batch", "inter_doc"], "inter_doc"),
        (["inter_doc", "thread_update"], "thread_update"),
        (["intra_batch", "thread_update"], "thread_update"),
    ]
    same_title = "t"
    same_existing = "ee4b01d3-d27f-46c5-8abc-82be1f70a9c0"
    for scopes, winner in cases:
        conflicts = [
            {"scope": s, "task_title": same_title, "source_b_ref": same_existing}
            for s in scopes
        ]
        out = _dedup_conflicts_by_pair(conflicts)
        assert len(out) == 1, f"failed for scopes={scopes}"
        assert out[0]["scope"] == winner, f"scopes={scopes}: expected {winner}, got {out[0]['scope']}"


def test_dedup_passes_through_conflicts_without_derivable_pair() -> None:
    """Conflicts missing task_title or B-side cannot be deduped safely; they
    must pass through unchanged (no silent loss)."""
    from app.pipeline.nodes.validate_tasks import _dedup_conflicts_by_pair

    conflicts = [
        {"scope": "multi_source", "task_title": "", "source_b_ref": "ee4b01d3-d27f-46c5-8abc-82be1f70a9c0"},
        {"scope": "thread_update", "task_title": "x", "source_b_ref": None, "task_id_b": None},
    ]
    out = _dedup_conflicts_by_pair(conflicts)
    assert len(out) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2.2 — utility used above (positioned at bottom because it's reused
# by all multi-source tests).
# ─────────────────────────────────────────────────────────────────────────────


def _make_policy_stub(*, ms_threshold: float = 0.85, lookback: int = 30):
    """Construct a frozen PipelinePolicy for tests — bypasses YAML / settings
    so unit tests are deterministic regardless of env."""
    from app.pipeline.policy import PipelinePolicy

    return PipelinePolicy(
        version="policy_test",
        confidence_abstain_threshold=0.55,
        confidence_uncertain_threshold=0.76,
        conflict_title_similarity_threshold=0.7,
        multi_source_title_similarity_threshold=ms_threshold,
        multi_source_conflict_lookback_days=lookback,
        max_conflict_checks_per_task=5,
        extraction_guidance="",
        validate_evidence_in_source=True,
    )

