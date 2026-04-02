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
        }
    )
    assert result.get("should_stop") is False
    assert result.get("extracted_tasks") == []
    assert result.get("saved_task_ids") == []
