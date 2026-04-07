from importlib import import_module

from app.pipeline.graph import pipeline


def _mock_save_sync(state):
    return {"saved_task_ids": [], "errors": list(state.get("errors", []))}


def test_pipeline_short_circuits_to_save_when_parse_fails(monkeypatch) -> None:
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    monkeypatch.setattr(save_mod, "save_tasks_sync", _mock_save_sync)
    result = pipeline.invoke(
        {
            "user_id": "u1",
            "source_doc_id": "d1",
            "source_type": "upload",
            "raw_content": "not-bytes",
            "metadata": {"file_name": "file.pdf"},
            "errors": [],
            "should_stop": False,
        }
    )
    assert result.get("should_stop") is True
    assert result.get("saved_task_ids") == []
    assert result.get("notifications_sent") == []


def test_pipeline_routes_from_extract_to_save_when_no_tasks(monkeypatch) -> None:
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    monkeypatch.setattr(save_mod, "save_tasks_sync", _mock_save_sync)
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    monkeypatch.setattr(extract_module, "call_llm", lambda *_args, **_kwargs: "[]")
    result = pipeline.invoke(
        {
            "user_id": "u1",
            "source_doc_id": "d2",
            "source_type": "gmail",
            "raw_content": "<p>Hello world</p>",
            "errors": [],
            "should_stop": False,
            "existing_tasks": [],
        }
    )
    assert result.get("should_stop") is False
    assert result.get("extracted_tasks") == []
    assert result.get("saved_task_ids") == []


def test_pipeline_full_flow_with_mock_llm_and_mock_mcp(monkeypatch) -> None:
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")
    extract_mod = import_module("app.pipeline.nodes.extract_tasks")
    normalize_mod = import_module("app.pipeline.nodes.normalize_tasks")
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")

    monkeypatch.setattr(
        save_mod,
        "save_tasks_sync",
        lambda _state: {"saved_task_ids": ["t-1"], "errors": []},
    )
    monkeypatch.setattr(
        dispatch_mod,
        "dispatch_notifications_sync",
        lambda _state: {"notifications_sent": [{"task_id": "t-1", "type": "calendar", "event_id": "evt-1"}], "errors": []},
    )
    monkeypatch.setattr(
        extract_mod,
        "call_llm",
        lambda *_args, **_kwargs: '[{"title":"Submit report","deadline_raw":"2026-04-30","assignee_raw":"Alice","priority_raw":"high"}]',
    )
    monkeypatch.setattr(
        normalize_mod,
        "call_llm",
        lambda *_args, **_kwargs: '[{"title":"Submit report","assignee":"Alice","deadline":"2026-04-30","priority":"high"}]',
    )
    monkeypatch.setattr(
        validate_mod,
        "call_llm",
        lambda *_args, **_kwargs: '{"conflict_type":"no_conflict","description":null}',
    )

    result = pipeline.invoke(
        {
            "user_id": "u1",
            "access_token": "tok",
            "source_doc_id": "d3",
            "source_type": "gmail",
            "raw_content": "<p>Please submit report by 2026-04-30</p>",
            "metadata": {"sender": "boss@example.com", "sent_at": "2026-04-01T10:00:00Z"},
            "errors": [],
            "should_stop": False,
            "existing_tasks": [],
        }
    )

    assert result.get("should_stop") is False
    assert len(result.get("extracted_tasks", [])) == 1
    assert len(result.get("normalized_tasks", [])) == 1
    assert len(result.get("validated_tasks", [])) == 1
    assert result.get("saved_task_ids") == ["t-1"]
    assert result.get("notifications_sent", [])[0]["event_id"] == "evt-1"
