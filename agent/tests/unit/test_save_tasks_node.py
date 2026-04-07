from importlib import import_module


def test_save_tasks_delegates_to_service(monkeypatch) -> None:
    calls = {}

    def _fake_sync(state):
        calls["state"] = state
        return {"saved_task_ids": ["t1"], "errors": []}

    save_tasks_module = import_module("app.pipeline.nodes.save_tasks")
    monkeypatch.setattr(save_tasks_module, "save_tasks_sync", _fake_sync)
    save_tasks = save_tasks_module.save_tasks
    result = save_tasks(
        {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "source_doc_id": "22222222-2222-2222-2222-222222222222",
            "validated_tasks": [],
        }
    )
    assert result["saved_task_ids"] == ["t1"]
    assert calls["state"]["user_id"] == "11111111-1111-1111-1111-111111111111"
