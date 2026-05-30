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
        folder: str = "inbox",
    ) -> list[dict[str, Any]]:
        """List Gmail messages in either the inbox or the sent folder.

        ``folder`` (Round 11, 2026-05-30) controls the Gmail query operator:

          * ``"inbox"`` (default) — ``in:inbox`` with category and noise
            filters applied. Matches the original behaviour exactly; existing
            callers that don't pass ``folder`` are unaffected.
          * ``"sent"`` — ``in:sent`` with no category filters (sent mail isn't
            categorised in Gmail's primary/promotions/updates buckets) and
            no noise filters (those target promotional mail, not outgoing).
            Used by the Team-mode Lead persona to surface delegations
            (tasks the user sent to teammates) in ``/team``.
        """
        after_ts = int(last_sync_at.timestamp()) if last_sync_at else 0
        if folder == "sent":
            base = "in:sent"
        else:
            _noise = "-category:promotions -category:updates -category:social -category:forums"
            if sync_profile == "broad":
                base = f"in:inbox {_noise}"
            else:
                base = f"in:inbox category:primary {_noise}"
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

    async def send_message(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> dict[str, Any]:
        """Send an email via the Gmail MCP. Requires the gmail.send scope.

        ``From`` is omitted so Gmail uses the authenticated account. Used by the
        Weekly Brief to self-send the manager their digest.
        """
        args: dict[str, Any] = {"to": to, "subject": subject, "body_html": body_html}
        if body_text is not None:
            args["body_text"] = body_text
        return await self.call_tool("send_message", args)
