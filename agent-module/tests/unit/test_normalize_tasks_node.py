from importlib import import_module

from app.pipeline.nodes.normalize_tasks import normalize_tasks


def test_normalize_tasks_llm_success(monkeypatch) -> None:
    module = import_module("app.pipeline.nodes.normalize_tasks")

    def _fake_call_llm(_prompt: str, temperature: float = 0.0) -> str:
        _ = temperature
        return '[{"title":"Submit report","assignee":"Bob","deadline":"2026-04-05","priority":"high"}]'

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Submit report",
                    "assignee_raw": "Bob",
                    "deadline_raw": "this Friday",
                    "priority_raw": "urgent",
                }
            ],
            "metadata": {"sent_at": "2026-04-01T10:00:00Z"},
            "errors": [],
        }
    )
    assert result["normalized_tasks"][0]["deadline"] == "2026-04-05"
    assert result["errors"] == []


def test_normalize_tasks_fallback_after_retries(monkeypatch) -> None:
    module = import_module("app.pipeline.nodes.normalize_tasks")
    calls = {"count": 0}

    def _fake_call_llm(_prompt: str, temperature: float = 0.0) -> str:
        _ = temperature
        calls["count"] += 1
        return "invalid-json"

    monkeypatch.setattr(module, "call_llm", _fake_call_llm)
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Do work",
                    "assignee_raw": "Alice",
                    "deadline_raw": "not-iso",
                    "priority_raw": "urgent",
                }
            ],
            "errors": [],
        }
    )
    assert calls["count"] == 3
    assert result["normalized_tasks"][0]["assignee"] == "Alice"
    assert result["normalized_tasks"][0]["deadline"] is None
    assert result["normalized_tasks"][0]["priority"] == "high"
    assert result["errors"]
