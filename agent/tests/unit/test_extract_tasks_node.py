from importlib import import_module

from app.pipeline.nodes.extract_tasks import extract_tasks, parse_extraction_response


def test_parse_extraction_response_filters_invalid_items() -> None:
    raw = '[{"title":"Do A","assignee_raw":"Ann","deadline_raw":null,"priority_raw":null},{"title":""},{}]'
    parsed = parse_extraction_response(raw)
    assert parsed == [
        {
            "title": "Do A",
            "assignee_raw": "Ann",
            "deadline_raw": None,
            "priority_raw": None,
        }
    ]


def test_extract_tasks_retries_until_valid(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    calls = {"count": 0}

    def _fake_call_llm(_prompt: str, temperature: float = 0.0) -> str:
        _ = temperature
        calls["count"] += 1
        if calls["count"] < 3:
            return "not-json"
        return '[{"title":"Submit report","assignee_raw":"Bob","deadline_raw":"Friday","priority_raw":"high"}]'

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


def test_extract_tasks_merges_chunk_results_without_duplicates(monkeypatch) -> None:
    extract_module = import_module("app.pipeline.nodes.extract_tasks")
    responses = iter(
        [
            '[{"title":"Submit report","assignee_raw":"Bob","deadline_raw":"Friday","priority_raw":"high"}]',
            '[{"title":"submit report","assignee_raw":"Bob","deadline_raw":"Friday","priority_raw":"high"},{"title":"Prepare slides","assignee_raw":null,"deadline_raw":null,"priority_raw":null}]',
        ]
    )

    def _fake_call_llm(_prompt: str, temperature: float = 0.0) -> str:
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
