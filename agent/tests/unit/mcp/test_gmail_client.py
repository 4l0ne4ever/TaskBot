from datetime import UTC, datetime

import pytest

from app.mcp.gmail_client import GmailMCPClient


@pytest.mark.asyncio
async def test_list_messages_builds_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    captured: dict = {}

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "list_messages"
        captured["query"] = args["query"]
        return {"messages": [{"id": "m1"}]}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    data = await client.list_messages(last_sync_at=datetime(2026, 4, 1, tzinfo=UTC), max_results=10)
    assert data == [{"id": "m1"}]
    q = captured["query"]
    assert "after:" in q
    assert "category:primary" in q
    assert "-category:promotions" in q
    assert "-category:social" in q
    assert "-category:updates" in q


@pytest.mark.asyncio
async def test_list_messages_profile_strict_work_primary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    captured: dict = {}

    async def _fake_call_tool(self, tool_name, args):
        captured["query"] = args["query"]
        return {"messages": []}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    await client.list_messages(sync_profile="strict_work")
    assert "category:primary" in captured["query"]
    assert "-category:social" in captured["query"]


@pytest.mark.asyncio
async def test_list_messages_profile_broad_excludes_noise(monkeypatch: pytest.MonkeyPatch) -> None:
    """broad profile skips category:primary filter (catch-all inbox) but still
    excludes promotions, social, updates, forums."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    captured: dict = {}

    async def _fake_call_tool(self, tool_name, args):
        captured["query"] = args["query"]
        return {"messages": []}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    await client.list_messages(sync_profile="broad")
    q = captured["query"]
    assert "category:primary" not in q, "broad catches all inbox, not just primary"
    assert "-category:promotions" in q
    assert "-category:social" in q
    assert "-category:updates" in q


@pytest.mark.asyncio
async def test_get_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "get_message"
        assert args["message_id"] == "abc"
        return {"id": "abc", "subject": "Test"}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    data = await client.get_message("abc")
    assert data["id"] == "abc"


@pytest.mark.asyncio
async def test_get_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "get_attachment"
        assert args["message_id"] == "m1"
        assert args["attachment_id"] == "a1"
        return {"data": "base64", "mime_type": "application/pdf"}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    data = await client.get_attachment("m1", "a1")
    assert data["mime_type"] == "application/pdf"
