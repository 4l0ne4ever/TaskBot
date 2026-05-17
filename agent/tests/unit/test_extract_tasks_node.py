from importlib import import_module

from app.pipeline.nodes.extract_tasks import (
    _build_extraction_prompt,
    _structural_item_count,
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
    """Retries on malformed JSON, then succeeds."""

    extract_module = import_module("app.pipeline.nodes.extract_tasks")

    class _StubPolicy:
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _StubPolicy())
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

    class _StubPolicy:
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _StubPolicy())
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

    class _StubPolicy:
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _StubPolicy())
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

    class _StubPolicy:
        validate_evidence_in_source = False
        extraction_guidance = ""
        version = "test"

    monkeypatch.setattr(extract_module, "get_pipeline_policy", lambda: _StubPolicy())
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
    assert "final resolved state" in user_prompt
