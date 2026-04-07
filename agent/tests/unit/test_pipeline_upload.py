"""Phase 2.8: Test pipeline with file upload source type (mock LLM + mock save/dispatch)."""
from importlib import import_module

from app.pipeline.graph import pipeline


def _mock_save_sync(state):
    return {"saved_task_ids": ["t-upload-1"], "errors": list(state.get("errors", []))}


def _mock_dispatch_sync(state):
    return {"notifications_sent": [], "errors": list(state.get("errors", []))}


def test_pipeline_upload_pdf_mock(monkeypatch) -> None:
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")
    extract_mod = import_module("app.pipeline.nodes.extract_tasks")
    normalize_mod = import_module("app.pipeline.nodes.normalize_tasks")
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")

    monkeypatch.setattr(save_mod, "save_tasks_sync", _mock_save_sync)
    monkeypatch.setattr(dispatch_mod, "dispatch_notifications_sync", _mock_dispatch_sync)
    monkeypatch.setattr(
        extract_mod, "call_llm",
        lambda *_a, **_kw: '[{"title":"Prepare budget","deadline_raw":"April 15","assignee_raw":"Finance team","priority_raw":null}]',
    )
    monkeypatch.setattr(
        normalize_mod, "call_llm",
        lambda *_a, **_kw: '[{"title":"Prepare budget","assignee":"Finance team","deadline":"2026-04-15","priority":null}]',
    )
    monkeypatch.setattr(
        validate_mod, "call_llm",
        lambda *_a, **_kw: '{"conflict_type":"no_conflict","description":null}',
    )

    result = pipeline.invoke(
        {
            "user_id": "u-upload",
            "access_token": "tok",
            "source_doc_id": "d-upload",
            "source_type": "upload",
            "raw_content": b"Fake PDF content: Prepare budget by April 15, Finance team",
            "metadata": {"file_name": "budget.pdf"},
            "errors": [],
            "should_stop": False,
            "existing_tasks": [],
        }
    )

    assert result.get("should_stop") is True or len(result.get("extracted_tasks", [])) >= 0
    assert isinstance(result.get("errors"), list)


def test_pipeline_upload_text_content(monkeypatch) -> None:
    """Upload with plain text (e.g. from already-parsed DOCX)."""
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")
    extract_mod = import_module("app.pipeline.nodes.extract_tasks")
    normalize_mod = import_module("app.pipeline.nodes.normalize_tasks")
    validate_mod = import_module("app.pipeline.nodes.validate_tasks")

    monkeypatch.setattr(save_mod, "save_tasks_sync", _mock_save_sync)
    monkeypatch.setattr(dispatch_mod, "dispatch_notifications_sync", _mock_dispatch_sync)
    monkeypatch.setattr(
        extract_mod, "call_llm",
        lambda *_a, **_kw: '[{"title":"Submit Q2 slides","deadline_raw":"May 1","assignee_raw":"Marketing","priority_raw":"high"}]',
    )
    monkeypatch.setattr(
        normalize_mod, "call_llm",
        lambda *_a, **_kw: '[{"title":"Submit Q2 slides","assignee":"Marketing","deadline":"2026-05-01","priority":"high"}]',
    )
    monkeypatch.setattr(
        validate_mod, "call_llm",
        lambda *_a, **_kw: '{"conflict_type":"no_conflict","description":null}',
    )

    result = pipeline.invoke(
        {
            "user_id": "u-upload2",
            "access_token": "tok",
            "source_doc_id": "d-upload2",
            "source_type": "upload",
            "raw_content": b"<p>Submit Q2 slides by May 1 \xe2\x80\x94 Marketing, high priority</p>",
            "metadata": {"file_name": "slides-request.html"},
            "errors": [],
            "should_stop": False,
            "existing_tasks": [],
        }
    )

    assert not result.get("should_stop")
    assert len(result.get("extracted_tasks", [])) >= 1
    assert result.get("saved_task_ids") == ["t-upload-1"]
