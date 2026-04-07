from importlib import import_module


def test_dispatch_notifications_delegates_to_service(monkeypatch) -> None:
    node_mod = import_module("app.pipeline.nodes.dispatch_notifications")
    calls = {}

    def _fake_dispatch(state):
        calls["state"] = state
        return {"notifications_sent": [{"task_id": "1", "type": "calendar"}], "errors": []}

    monkeypatch.setattr(node_mod, "dispatch_notifications_sync", _fake_dispatch)
    result = node_mod.dispatch_notifications({"saved_task_ids": ["1"]})
    assert result["notifications_sent"][0]["type"] == "calendar"
    assert calls["state"]["saved_task_ids"] == ["1"]
