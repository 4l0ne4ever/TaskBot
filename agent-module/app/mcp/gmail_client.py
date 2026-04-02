from datetime import datetime
from typing import Any

from app.config import get_settings
from app.mcp.base_client import BaseMCPClient


class GmailMCPClient(BaseMCPClient):
    def __init__(self, access_token: str):
        settings = get_settings()
        super().__init__(server_url=settings.gmail_mcp_url, access_token=access_token)

    async def list_messages(
        self,
        *,
        last_sync_at: datetime | None = None,
        max_results: int = 50,
        label: str = "INBOX",
    ) -> list[dict[str, Any]]:
        after_ts = int(last_sync_at.timestamp()) if last_sync_at else 0
        query = f"after:{after_ts} in:{label.lower()}" if after_ts > 0 else f"in:{label.lower()}"
        result = await self.call_tool(
            "list_messages",
            {"query": query, "max_results": max_results},
        )
        messages = result.get("messages") or result.get("data") or []
        return messages if isinstance(messages, list) else []

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self.call_tool(
            "get_message",
            {"message_id": message_id, "format": "full"},
        )

    async def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        return await self.call_tool(
            "get_attachment",
            {"message_id": message_id, "attachment_id": attachment_id},
        )
