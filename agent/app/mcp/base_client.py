import json
from typing import Any

import httpx


class MCPClientError(RuntimeError):
    pass


class BaseMCPClient:
    def __init__(self, server_url: str, access_token: str, timeout_seconds: int = 30):
        self.server_url = server_url
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        payload = {"tool_name": tool_name, "arguments": args}
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(self.server_url, headers=headers, json=payload)

        if resp.status_code >= 400:
            raise MCPClientError(f"MCP call failed [{resp.status_code}]: {resp.text}")

        data = resp.json()
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError as exc:
                raise MCPClientError("MCP response is not valid JSON") from exc
        raise MCPClientError("Unsupported MCP response format")
