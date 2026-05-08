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
        module,
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
    monkeypatch.setattr(module, "call_llm", lambda *_args, **_kwargs: "invalid-json")

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

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)
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
        module,
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

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)

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
        module,
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

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)

    from app.pipeline import policy as policy_mod

    base_policy = policy_mod.get_pipeline_policy()
    capped = base_policy.__class__(
        version=base_policy.version,
        confidence_abstain_threshold=base_policy.confidence_abstain_threshold,
        confidence_uncertain_threshold=base_policy.confidence_uncertain_threshold,
        conflict_title_similarity_threshold=0.5,
        max_conflict_checks_per_task=1,
        extraction_guidance=base_policy.extraction_guidance,
        verification_enabled=base_policy.verification_enabled,
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
