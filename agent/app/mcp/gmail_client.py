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
        sync_profile: str = "balanced",
    ) -> list[dict[str, Any]]:
        after_ts = int(last_sync_at.timestamp()) if last_sync_at else 0
        if sync_profile == "strict_work":
            base = "in:inbox category:primary -category:promotions -category:updates -category:forums"
        elif sync_profile == "broad":
            base = "in:inbox"
        else:
            base = "in:inbox (category:primary OR category:social) -category:promotions -category:updates -category:forums"
        query = f"after:{after_ts} {base}" if after_ts > 0 else base
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
