from datetime import UTC, datetime

import pytest

from app.mcp.drive_client import DriveMCPClient


@pytest.mark.asyncio
async def test_list_files_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")
    monkeypatch.setenv("DRIVE_MCP_URL", "https://drive.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "list_files"
        assert "modifiedTime >" in args["query"]
        return {"files": [{"id": "f1"}], "next_page_token": "token-1"}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = DriveMCPClient(access_token="token")
    result = await client.list_files(last_sync_at=datetime(2026, 4, 1, tzinfo=UTC))
    assert result["files"][0]["id"] == "f1"


@pytest.mark.asyncio
async def test_list_shared_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")
    monkeypatch.setenv("DRIVE_MCP_URL", "https://drive.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "list_shared_files"
        assert "sharedWithMe=true" in args["query"]
        return {"files": [{"id": "sf1"}]}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = DriveMCPClient(access_token="token")
    result = await client.list_shared_files(last_sync_at=datetime(2026, 4, 1, tzinfo=UTC))
    assert result["files"][0]["id"] == "sf1"


@pytest.mark.asyncio
async def test_get_file_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GMAIL_MCP_URL", "https://gmail.mcp.test/mcp")
    monkeypatch.setenv("DRIVE_MCP_URL", "https://drive.mcp.test/mcp")

    async def _fake_call_tool(self, tool_name, args):
        assert tool_name == "get_file_content"
        assert args["file_id"] == "file-1"
        return {"content": "base64", "mime_type": "application/pdf"}

    monkeypatch.setattr("app.mcp.base_client.BaseMCPClient.call_tool", _fake_call_tool)

    client = DriveMCPClient(access_token="token")
    result = await client.get_file_content("file-1")
    assert result["mime_type"] == "application/pdf"
