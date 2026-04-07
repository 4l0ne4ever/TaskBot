from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_mcp_missing_auth() -> None:
    client = TestClient(app)
    r = client.post("/mcp", json={"tool_name": "list_files", "arguments": {}})
    assert r.status_code == 401


def test_mcp_unknown_tool() -> None:
    client = TestClient(app)
    r = client.post(
        "/mcp",
        headers={"Authorization": "Bearer x"},
        json={"tool_name": "nope", "arguments": {}},
    )
    assert r.status_code == 400
