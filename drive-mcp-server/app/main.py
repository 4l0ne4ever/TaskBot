"""
HTTP MCP bridge for Google Drive — same request shape as agent.app.mcp.BaseMCPClient:
POST { "tool_name": str, "arguments": dict } with Authorization: Bearer <user Google access token>.
Calls Google Drive API v3 (no service account; token is end-user OAuth).
"""
from __future__ import annotations

import base64
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"

app = FastAPI(title="TaskBot Drive MCP (HTTP)")


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization bearer token")
    return auth.removeprefix("Bearer ").strip()


def _drive_fields_param(client_fields: str | None) -> str:
    inner = (client_fields or "id,name,mimeType,modifiedTime,size").strip()
    return f"nextPageToken, files({inner})"


def _google_apps_export_mime(native_mime: str) -> str | None:
    """Return export mime for Google-native files, or None if not exportable via Drive export API."""
    if native_mime in (
        "application/vnd.google-apps.folder",
        "application/vnd.google-apps.shortcut",
    ):
        return None
    if native_mime.startswith("application/vnd.google-apps."):
        return "application/pdf"
    return None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_invoke(request: Request) -> dict[str, Any]:
    token = _bearer(request)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    tool_name = body.get("tool_name")
    args = body.get("arguments") if isinstance(body.get("arguments"), dict) else {}

    if not tool_name or not isinstance(tool_name, str):
        raise HTTPException(status_code=400, detail="Missing tool_name")

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        if tool_name == "list_files":
            q = str(args.get("query") or "")
            fields = _drive_fields_param(args.get("fields"))
            page_size = int(args.get("page_size") or 50)
            resp = await client.get(
                DRIVE_FILES,
                params={
                    "q": q,
                    "fields": fields,
                    "pageSize": page_size,
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                },
                headers=headers,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            return {
                "files": data.get("files") or [],
                "nextPageToken": data.get("nextPageToken"),
                "next_page_token": data.get("nextPageToken"),
            }

        if tool_name == "list_shared_files":
            q = str(args.get("query") or "")
            fields = _drive_fields_param(args.get("fields"))
            page_size = int(args.get("page_size") or 100)
            resp = await client.get(
                DRIVE_FILES,
                params={
                    "q": q,
                    "fields": fields,
                    "pageSize": page_size,
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                },
                headers=headers,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            return {
                "files": data.get("files") or [],
                "nextPageToken": data.get("nextPageToken"),
                "next_page_token": data.get("nextPageToken"),
            }

        if tool_name == "get_file_content":
            file_id = args.get("file_id")
            if not file_id or not isinstance(file_id, str):
                raise HTTPException(status_code=400, detail="Missing file_id")

            meta_resp = await client.get(
                f"{DRIVE_FILES}/{file_id}",
                params={"fields": "mimeType,name"},
                headers=headers,
            )
            if meta_resp.status_code >= 400:
                raise HTTPException(status_code=meta_resp.status_code, detail=meta_resp.text)
            meta = meta_resp.json()
            mime = meta.get("mimeType") or "application/octet-stream"

            export_as = _google_apps_export_mime(mime)
            if export_as is None and mime.startswith("application/vnd.google-apps."):
                raise HTTPException(
                    status_code=400,
                    detail="Google Drive native type is not exportable (e.g. folder or shortcut); use a binary or Docs/Sheets/Slides file.",
                )

            if export_as:
                media_resp = await client.get(
                    f"{DRIVE_FILES}/{file_id}/export",
                    params={"mimeType": export_as},
                    headers=headers,
                )
                out_mime = export_as
            else:
                media_resp = await client.get(
                    f"{DRIVE_FILES}/{file_id}",
                    params={"alt": "media"},
                    headers=headers,
                )
                out_mime = mime
            if media_resp.status_code >= 400:
                raise HTTPException(status_code=media_resp.status_code, detail=media_resp.text)

            return {
                "file_id": file_id,
                "mime_type": out_mime,
                "name": meta.get("name"),
                "content_base64": base64.standard_b64encode(media_resp.content).decode("ascii"),
            }

        raise HTTPException(status_code=400, detail=f"Unknown tool_name: {tool_name}")
