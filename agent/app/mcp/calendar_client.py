from typing import Any

from app.config import get_settings
from app.mcp.base_client import BaseMCPClient


class CalendarMCPClient(BaseMCPClient):
    def __init__(self, access_token: str):
        settings = get_settings()
        super().__init__(server_url=settings.calendar_mcp_url, access_token=access_token)

    async def create_event(self, *, title: str, date_iso: str, description: str | None = None) -> dict[str, Any]:
        return await self.call_tool(
            "create_event",
            {"title": title, "date": date_iso, "description": description},
        )

    async def update_event(
        self,
        *,
        event_id: str,
        title: str,
        date_iso: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        return await self.call_tool(
            "update_event",
            {"event_id": event_id, "title": title, "date": date_iso, "description": description},
        )
