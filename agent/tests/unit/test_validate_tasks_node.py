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
                {"title": "Submit Q1 report", "assignee": "Bob", "deadline": "2026-04-05", "source_ref": "new-1"}
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
