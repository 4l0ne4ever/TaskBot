from datetime import datetime
from typing import Any

from app.config import get_settings
from app.mcp.base_client import BaseMCPClient


class DriveMCPClient(BaseMCPClient):
    def __init__(self, access_token: str):
        settings = get_settings()
        super().__init__(server_url=settings.drive_mcp_url, access_token=access_token)

    async def list_files(
        self,
        *,
        last_sync_at: datetime | None = None,
        page_size: int = 50,
        sync_profile: str = "balanced",
    ) -> dict[str, Any]:
        last_sync_iso = (last_sync_at.isoformat() if last_sync_at else "1970-01-01T00:00:00Z")
        if sync_profile == "broad":
            mime_clause = (
                "mimeType='application/pdf' or "
                "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType='application/vnd.google-apps.document' or "
                "mimeType='application/vnd.google-apps.spreadsheet' or "
                "mimeType='application/vnd.google-apps.presentation'"
            )
        else:
            mime_clause = (
                "mimeType='application/pdf' or "
                "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType='application/vnd.google-apps.document'"
            )
        query = (
            f"modifiedTime > '{last_sync_iso}' and trashed=false and "
            "mimeType!='application/vnd.google-apps.folder' and "
            "mimeType!='application/vnd.google-apps.shortcut' and "
            f"({mime_clause})"
        )
        return await self.call_tool(
            "list_files",
            {
                "query": query,
                "fields": "id,name,mimeType,modifiedTime,size",
                "page_size": page_size,
            },
        )

    async def list_shared_files(
        self,
        *,
        last_sync_at: datetime | None = None,
        page_size: int = 50,
        sync_profile: str = "balanced",
    ) -> dict[str, Any]:
        last_sync_iso = (last_sync_at.isoformat() if last_sync_at else "1970-01-01T00:00:00Z")
        if sync_profile == "strict_work":
            mime_clause = (
                "mimeType='application/pdf' or "
                "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
            )
        elif sync_profile == "broad":
            mime_clause = (
                "mimeType='application/pdf' or "
                "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType='application/vnd.google-apps.document' or "
                "mimeType='application/vnd.google-apps.spreadsheet' or "
                "mimeType='application/vnd.google-apps.presentation'"
            )
        else:
            mime_clause = (
                "mimeType='application/pdf' or "
                "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType='application/vnd.google-apps.document'"
            )
        # Product-grade query: avoid folders/shortcuts/trashed and keep only supported document types.
        query = (
            f"sharedWithMe=true and modifiedTime > '{last_sync_iso}' and trashed=false and "
            "mimeType!='application/vnd.google-apps.folder' and "
            "mimeType!='application/vnd.google-apps.shortcut' and "
            f"({mime_clause})"
        )
        return await self.call_tool(
            "list_shared_files",
            {"query": query, "fields": "id,name,mimeType,modifiedTime,size", "page_size": page_size},
        )

    async def get_file_content(self, file_id: str) -> dict[str, Any]:
        return await self.call_tool("get_file_content", {"file_id": file_id})
