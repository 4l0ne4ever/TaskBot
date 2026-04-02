from datetime import UTC, datetime

import pytest

from app.mcp.gmail_client import GmailMCPClient


@pytest.mark.asyncio
async def test_list_messages_builds_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "list_messages"
        assert args["query"].startswith("after:")
        return {"messages": [{"id": "m1"}]}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = GmailMCPClient(access_token="token")
    data = await client.list_messages(last_sync_at=datetime(2026, 4, 1, tzinfo=UTC), max_results=10)
    assert data == [{"id": "m1"}]


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
