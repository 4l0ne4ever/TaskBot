"""
HTTP MCP bridge for Gmail — same request shape as agent.app.mcp.BaseMCPClient:
POST { "tool_name": str, "arguments": dict } with Authorization: Bearer <user Google access token>.
Calls Google Gmail API v1 (no service account; token is end-user OAuth).
"""
from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def _build_raw_message(
    *,
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    sender: str | None = None,
) -> str:
    """Build an RFC822 message, base64url-encoded for Gmail's ``raw`` field.

    Multipart/alternative with a plain-text fallback so clients without HTML
    still render something. ``sender`` is optional — Gmail uses the
    authenticated account when ``From`` is omitted, so we only set it when given.
    """
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if sender:
        msg["From"] = formataddr(("TaskBot", sender))
    msg.attach(MIMEText(body_text or "View this brief in an HTML-capable client.", "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

app = FastAPI(title="TaskBot Gmail MCP (HTTP)")


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization bearer token")
    return auth.removeprefix("Bearer ").strip()


def _extract_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if (h.get("name") or "").lower() == name.lower():
            return h.get("value") or ""
    return ""


def _decode_body_data(part: dict) -> str:
    data = (part.get("body") or {}).get("data") or ""
    if not data:
        return ""
    padded = data + "=" * (4 - len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    """Walk MIME tree and return text/html or text/plain body."""
    mime = payload.get("mimeType") or ""

    if mime == "text/html":
        return _decode_body_data(payload)
    if mime == "text/plain":
        text = _decode_body_data(payload)
        if text:
            return text

    for part in payload.get("parts") or []:
        result = _extract_body(part)
        if result:
            return result

    body_data = _decode_body_data(payload)
    if body_data:
        return body_data

    return ""


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

    async with httpx.AsyncClient(timeout=60.0) as client:
        if tool_name == "list_messages":
            query = str(args.get("query") or "in:inbox")
            max_results = min(int(args.get("max_results") or 50), 100)
            resp = await client.get(
                f"{GMAIL_API}/messages",
                params={"q": query, "maxResults": max_results},
                headers=headers,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            messages = data.get("messages") or []
            return {"messages": messages}

        if tool_name == "get_message":
            message_id = args.get("message_id")
            if not message_id or not isinstance(message_id, str):
                raise HTTPException(status_code=400, detail="Missing message_id")
            fmt = args.get("format") or "full"
            resp = await client.get(
                f"{GMAIL_API}/messages/{message_id}",
                params={"format": fmt},
                headers=headers,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            msg = resp.json()

            payload = msg.get("payload") or {}
            msg_headers = payload.get("headers") or []

            result: dict[str, Any] = {
                "id": msg.get("id"),
                "threadId": msg.get("threadId"),
                "internalDate": msg.get("internalDate"),
                "snippet": msg.get("snippet"),
                "subject": _extract_header(msg_headers, "Subject"),
                "from": _extract_header(msg_headers, "From"),
                "to": _extract_header(msg_headers, "To"),
                "date": _extract_header(msg_headers, "Date"),
                "headers": msg_headers,
                "body": _extract_body(payload),
            }
            return result

        if tool_name == "get_attachment":
            message_id = args.get("message_id")
            attachment_id = args.get("attachment_id")
            if not message_id or not attachment_id:
                raise HTTPException(status_code=400, detail="Missing message_id or attachment_id")
            resp = await client.get(
                f"{GMAIL_API}/messages/{message_id}/attachments/{attachment_id}",
                headers=headers,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

        if tool_name == "send_message":
            to = args.get("to")
            subject = args.get("subject")
            body_html = args.get("body_html")
            if not to or not isinstance(to, str):
                raise HTTPException(status_code=400, detail="Missing 'to'")
            if not subject or not isinstance(subject, str):
                raise HTTPException(status_code=400, detail="Missing 'subject'")
            if not body_html or not isinstance(body_html, str):
                raise HTTPException(status_code=400, detail="Missing 'body_html'")
            raw = _build_raw_message(
                to=to,
                subject=subject,
                body_html=body_html,
                body_text=args.get("body_text") if isinstance(args.get("body_text"), str) else None,
                sender=args.get("sender") if isinstance(args.get("sender"), str) else None,
            )
            resp = await client.post(
                f"{GMAIL_API}/messages/send",
                headers={**headers, "Content-Type": "application/json"},
                json={"raw": raw},
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            return {"id": data.get("id"), "threadId": data.get("threadId"), "labelIds": data.get("labelIds")}

        raise HTTPException(status_code=400, detail=f"Unknown tool_name: {tool_name}")
