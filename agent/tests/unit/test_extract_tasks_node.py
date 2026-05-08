from importlib import import_module

import pytest

from app.pipeline.nodes.extract_tasks import (
    _build_extraction_prompt,
    _structural_item_count,
    _verify_response_shape,
    extract_tasks,
    parse_extraction_response,
)


def test_parse_extraction_response_filters_invalid_items() -> None:
    raw = '{"tasks":[{"title":"Do A","assignee":"Ann","source_ref":"item-1","deadline":null,"priority":null},{"title":""},{}]}'
    parsed = parse_extraction_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Do A"
    assert parsed[0]["assignee"] == "Ann"
    assert parsed[0]["source_ref"] == "item-1"
    assert parsed[0]["deadline"] is None
    assert parsed[0]["priority"] is None


def test_parse_extraction_response_accepts_legacy_top_level_array() -> None:
    raw = '[{"title":"Legacy"}]'
    parsed = parse_extraction_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Legacy"


def test_parse_extraction_response_repairs_common_json_slips() -> None:
    raw = '```json\n{"tasks":[{"title":"Do A",}]}\n```'
    parsed = parse_extraction_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Do A"


def test_extract_tasks_retries_until_valid(monkeypatch) -> None:
    """Retries on malformed JSON, then succeeds.

    The policy's verification pass is intentionally disabled here so the
    assertion isolates the retry behaviour of ``_extract_with_retry`` and
    stays stable across policy default changes. Verification is covered
    separately by the ``_enable_verification`` tests below.
    """

    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _NoVerifyPolicy:
        verification_enabled = False
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _NoVerifyPolicy())
    calls = {"count": 0}

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        calls["count"] += 1
        if calls["count"] < 3:
            return "not-json"
        return '{"tasks":[{"title":"Submit report","assignee":"Bob","priority":"high"}]}'

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "cleaned_text": "Please submit report by Friday",
            "source_type": "gmail",
            "metadata": {},
            "errors": [],
        }
    )
    assert calls["count"] == 3
    assert len(result["extracted_tasks"]) == 1
    assert result["extracted_tasks"][0]["title"] == "Submit report"


def test_extract_tasks_repairs_before_retry(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _NoVerifyPolicy:
        verification_enabled = False
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _NoVerifyPolicy())
    calls = {"count": 0}

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        calls["count"] += 1
        return '{"tasks":[{"title":"Submit report",}]}'

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks({"cleaned_text": "Submit report", "source_type": "gmail", "metadata": {}, "errors": []})

    assert calls["count"] == 1
    assert result["extracted_tasks"][0]["title"] == "Submit report"


def test_extract_tasks_respects_configured_retry_limit(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _NoVerifyPolicy:
        verification_enabled = False
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _NoVerifyPolicy())
    monkeypatch.setattr(extract_module.settings, "extraction_max_retries", 1)
    calls = {"count": 0}

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        calls["count"] += 1
        return "not-json"

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks({"cleaned_text": "Submit report", "source_type": "gmail", "metadata": {}, "errors": []})

    assert calls["count"] == 1
    assert result["extracted_tasks"] == []
    assert any("after 1 attempts" in e for e in result["errors"])


def test_structural_item_count_uses_visible_list_shape_only() -> None:
    text = "1. A: prepare report\n2. B: prepare slides\n\nPlain paragraph\n- C: check metrics"
    assert _structural_item_count(text) == 3


def test_extract_tasks_retries_when_structured_list_is_undercovered(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _NoVerifyPolicy:
        verification_enabled = False
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _NoVerifyPolicy())
    responses = iter(
        [
            '{"tasks":[{"title":"Prepare report","assignee":"A"}]}',
            '{"tasks":[{"title":"Prepare report","assignee":"A"},{"title":"Prepare slides","assignee":"B"}]}',
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return next(responses)

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "cleaned_text": "1. A: prepare report\n2. B: prepare slides",
            "source_type": "gmail",
            "metadata": {},
            "errors": [],
        }
    )

    assert [t["title"] for t in result["extracted_tasks"]] == ["Prepare report", "Prepare slides"]


def test_extract_tasks_merges_chunk_results_without_duplicates(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    responses = iter(
        [
            '{"tasks":[{"title":"Submit report","assignee":"Bob"}]}',
            '{"tasks":[{"title":"submit report","assignee":"Bob"},{"title":"Prepare slides"}]}',
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return next(responses)

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "chunks": ["chunk1", "chunk2"],
            "source_type": "upload",
            "metadata": {},
            "errors": [],
        }
    )
    titles = [task["title"] for task in result["extracted_tasks"]]
    assert titles == ["Submit report", "Prepare slides"]


def test_extract_tasks_preserves_source_ref_through_merge(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    responses = iter(
        [
            '{"tasks":[{"title":"Submit report","assignee":"Bob","source_ref":"item-1"}]}',
            '{"tasks":[{"title":"submit report","assignee":"Bob","source_ref":"item-1b"}]}',
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return next(responses)

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "chunks": ["chunk1", "chunk2"],
            "source_type": "upload",
            "metadata": {},
            "errors": [],
        }
    )

    assert result["extracted_tasks"][0]["source_ref"] == "item-1"


def test_extract_tasks_keeps_distinct_actions_separate(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return (
            '{"tasks":[{"title":"Review doc A"},'
            '{"title":"Update spreadsheet B"},'
            '{"title":"Send to Nguyen by Friday","assignee":"Nguyen"}]}'
        )

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "cleaned_text": "Please review doc A, update spreadsheet B, and send to Nguyen by Friday.",
            "source_type": "gmail",
            "metadata": {},
            "errors": [],
        }
    )
    titles = [task["title"] for task in result["extracted_tasks"]]
    assert titles == ["Review doc A", "Update spreadsheet B", "Send to Nguyen by Friday"]


def test_extraction_prompt_is_instruction_only_and_bounds_source_text(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _NoGuidancePolicy:
        verification_enabled = False
        validate_evidence_in_source = True
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _NoGuidancePolicy())
    system_prompt, user_prompt = _build_extraction_prompt(
        {
            "cleaned_text": "Just pushed code to feature/auth. Feel free to pull and test.",
            "source_type": "gmail",
            "metadata": {"sent_at": "2026-04-20", "sender": "dev@example.com", "subject": "FYI"},
            "errors": [],
        },
        "Just pushed code to feature/auth. Feel free to pull and test.",
    )

    assert "deterministic task extraction function" in system_prompt
    assert "<taskbot_text>" in user_prompt
    assert "</taskbot_text>" in user_prompt
    assert "--- Examples" not in user_prompt
    assert "Example:" not in user_prompt
    assert "Output:" not in user_prompt
    assert "hoàn thành bản đánh giá nhân sự" not in user_prompt


def test_extraction_prompt_covers_lists_threads_and_delegated_performers(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _GuidancePolicy:
        verification_enabled = False
        validate_evidence_in_source = True
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _GuidancePolicy())
    _system_prompt, user_prompt = _build_extraction_prompt(
        {
            "source_type": "gmail",
            "metadata": {"sent_at": "2026-04-06", "sender": "lead@example.com", "subject": "Thread"},
            "errors": [],
        },
        "Email thread:\n[Email 1]\nA owns report.\n[Email 2]\nB now owns report.",
    )

    assert '"source_ref"' in user_prompt
    assert "numbered lists" in user_prompt
    assert "open checklist rows" in user_prompt
    assert "named performer is the assignee" in user_prompt
    assert "changes the assignee or deadline" in user_prompt


class _StubPolicy:
    """Minimal policy stub that enables verification without loading YAML."""

    verification_enabled = True
    validate_evidence_in_source = False
    extraction_guidance = ""
    version = "test"


@pytest.fixture
def _enable_verification(monkeypatch):
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _StubPolicy())
    return extract_module


def test_verify_response_shape_distinguishes_empty_from_malformed():
    """A valid `tasks: []` is intentional rejection; a malformed blob is a data loss risk."""
    is_valid, out = _verify_response_shape('{"tasks": []}')
    assert is_valid is True
    assert out == []

    is_valid, out = _verify_response_shape("not-json")
    assert is_valid is False
    assert out == []

    is_valid, out = _verify_response_shape("null")
    assert is_valid is False

    is_valid, out = _verify_response_shape('{"something_else": 1}')
    assert is_valid is False


def test_verify_falls_back_to_pre_verify_when_response_malformed(_enable_verification, monkeypatch):
    """Regression: a malformed verify response must not wipe the extracted list."""
    extract_module = _enable_verification

    responses = iter(
        [
            '{"tasks":[{"title":"Submit report","assignee":"Bob"}]}',
            "not-json",
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return next(responses)

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "cleaned_text": "Please submit report by Friday",
            "source_type": "gmail",
            "metadata": {},
            "errors": [],
        }
    )
    titles = [t["title"] for t in result["extracted_tasks"]]
    assert titles == ["Submit report"]
    assert any("verification response unparseable" in e for e in result["errors"])


def test_verify_trusts_intentional_empty_rejection(_enable_verification, monkeypatch):
    """When the verifier legitimately returns `tasks: []`, we must honour it."""
    extract_module = _enable_verification

    responses = iter(
        [
            '{"tasks":[{"title":"Marketing idea"}]}',
            '{"tasks":[]}',
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0, **_kwargs) -> str:
        _ = temperature
        return next(responses)

    monkeypatch.setattr(extract_module, "call_llm", _fake_call_llm)
    result = extract_tasks(
        {
            "cleaned_text": "Just a fun marketing idea to discuss, no action yet.",
            "source_type": "gmail",
            "metadata": {},
            "errors": [],
        }
    )
    assert result["extracted_tasks"] == []
    assert not any("unparseable" in e for e in result["errors"])
