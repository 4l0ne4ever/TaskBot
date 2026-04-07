#!/usr/bin/env python3
"""
End-to-end checks against Google APIs and HTTP MCP endpoints using a real user access token.

Loads `.env` from the repository root (if present). Required for a full run:

  E2E_GOOGLE_ACCESS_TOKEN — OAuth access token (usually ~1h). Scopes depend on what you test:
    full script: Gmail + Drive + Calendar; with --gmail-only: Gmail is enough (e.g. gmail.readonly).

Optional:

  E2E_EXPECT_GOOGLE_EMAIL — if set, asserts account email (userinfo in full mode; Gmail profile in --gmail-only).
  GMAIL_MCP_URL, DRIVE_MCP_URL, CALENDAR_MCP_URL — same as agent (defaults match .env.example).

By default exits 0 when the token is missing (CI / local without secrets). Use --require-token
to fail if the token is not set.

Where to get a token (dev only, never commit it):
  - Google OAuth 2.0 Playground: https://developers.google.com/oauthplayground — chọn scope Gmail
    (ví dụ …/auth/gmail.readonly), bước 2 có thể dùng OAuth credentials của bạn để lấy access token.
  - Hoặc đăng nhập TaskBot / backend OAuth và copy access_token từ response (network tab / log tạm),
    lưu ý token sống ngắn.

Read-only by default: Drive MCP list (+ optional download), Gmail MCP list_messages, Calendar REST
calendarList. --gmail-only chỉ gọi Gmail (profile + hosted list_messages). --calendar-create-smoke
tạo một sự kiện thử trên Calendar MCP.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    load_dotenv(ROOT / ".env", override=False)


def _ok(name: str, detail: str = "") -> None:
    extra = f" — {detail}" if detail else ""
    print(f"OK  {name}{extra}")


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}", file=sys.stderr)


def _userinfo_email(token: str) -> tuple[bool, str]:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
    if r.status_code != 200:
        return False, f"userinfo HTTP {r.status_code}"
    data = r.json()
    email = (data.get("email") or "").strip()
    return True, email


def _check_email_expectation(token: str, expect: str) -> bool:
    ok, email = _userinfo_email(token)
    if not ok:
        _fail("userinfo", email)
        return False
    if email.lower() != expect.strip().lower():
        _fail("userinfo", f"email mismatch: got {email!r}, expected {expect!r}")
        return False
    _ok("userinfo", email)
    return True


def _gmail_profile_email(token: str) -> tuple[bool, str]:
    """Works with gmail.readonly (and similar); no userinfo.email scope required."""
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    if r.status_code != 200:
        return False, f"gmail profile HTTP {r.status_code}"
    data = r.json()
    email = (data.get("emailAddress") or "").strip()
    return True, email


def _check_gmail_profile_expectation(token: str, expect: str) -> bool:
    ok, email = _gmail_profile_email(token)
    if not ok:
        _fail("gmail profile", email)
        return False
    if email.lower() != expect.strip().lower():
        _fail("gmail profile", f"email mismatch: got {email!r}, expected {expect!r}")
        return False
    _ok("gmail profile", email)
    return True


def _drive_mcp_list_files(url: str, token: str) -> bool:
    body = {
        "tool_name": "list_files",
        "arguments": {
            "query": "mimeType='application/pdf'",
            "fields": "id,name,mimeType",
            "page_size": 5,
        },
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code != 200:
        _fail("drive_mcp list_files", f"HTTP {r.status_code} {r.text[:500]}")
        return False
    data = r.json()
    files = data.get("files") or []
    _ok("drive_mcp list_files", f"{len(files)} file(s) in first page")
    return True


def _drive_mcp_get_one_pdf(url: str, token: str) -> bool:
    list_body = {
        "tool_name": "list_files",
        "arguments": {
            "query": "mimeType='application/pdf'",
            "fields": "id,name,mimeType",
            "page_size": 1,
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url.rstrip("/"), headers=headers, json=list_body)
        if r.status_code != 200:
            _fail("drive_mcp get_file_content (list)", f"HTTP {r.status_code}")
            return False
        files = (r.json().get("files") or [])[:1]
        if not files:
            _ok("drive_mcp get_file_content", "skipped (no PDF in Drive to fetch)")
            return True
        fid = files[0].get("id")
        if not fid:
            _fail("drive_mcp get_file_content", "missing id on file entry")
            return False
        r2 = client.post(
            url.rstrip("/"),
            headers=headers,
            json={"tool_name": "get_file_content", "arguments": {"file_id": fid}},
        )
    if r2.status_code != 200:
        _fail("drive_mcp get_file_content", f"HTTP {r2.status_code} {r2.text[:300]}")
        return False
    payload = r2.json()
    raw = base64.standard_b64decode(payload.get("content_base64") or "")
    _ok("drive_mcp get_file_content", f"{len(raw)} bytes, mime={payload.get('mime_type')}")
    return True


def _gmail_mcp_list(url: str, token: str) -> bool:
    body = {
        "tool_name": "list_messages",
        "arguments": {"query": "in:inbox", "max_results": 3},
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code != 200:
        _fail("gmail_mcp list_messages", f"HTTP {r.status_code} {r.text[:500]}")
        return False
    try:
        data = r.json()
    except json.JSONDecodeError as exc:
        _fail("gmail_mcp list_messages", f"invalid JSON: {exc}")
        return False
    messages = data.get("messages") or data.get("data") or []
    n = len(messages) if isinstance(messages, list) else 0
    _ok("gmail_mcp list_messages", f"{n} message ref(s)")
    return True


def _calendar_rest_list(token: str) -> bool:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            params={"maxResults": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
    if r.status_code != 200:
        _fail("calendar REST calendarList", f"HTTP {r.status_code} {r.text[:400]}")
        return False
    items = (r.json().get("items") or [])
    _ok("calendar REST calendarList", f"{len(items)} calendar(s)")
    return True


def _calendar_mcp_create_smoke(url: str, token: str) -> bool:
    from datetime import datetime, timedelta, timezone

    day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    body = {
        "tool_name": "create_event",
        "arguments": {
            "title": "TaskBot MCP E2E (safe to delete)",
            "date": f"{day}T15:00:00Z",
            "description": "Created by scripts/mcp_real_account_check.py --calendar-create-smoke",
        },
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code != 200:
        _fail("calendar_mcp create_event", f"HTTP {r.status_code} {r.text[:500]}")
        return False
    data = r.json()
    eid = data.get("event_id") or data.get("id")
    _ok("calendar_mcp create_event", f"event_id={eid!r} (delete in Google Calendar if unwanted)")
    return True


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="MCP + Google E2E checks with a real access token.")
    parser.add_argument(
        "--require-token",
        action="store_true",
        help="Exit with error if E2E_GOOGLE_ACCESS_TOKEN is not set.",
    )
    parser.add_argument(
        "--with-drive-download",
        action="store_true",
        help="After list_files, call get_file_content on the first PDF (if any).",
    )
    parser.add_argument(
        "--calendar-create-smoke",
        action="store_true",
        help="POST create_event to CALENDAR_MCP_URL (writes one event).",
    )
    parser.add_argument(
        "--gmail-only",
        action="store_true",
        help="Only verify Gmail API profile + hosted Gmail MCP (token chỉ cần scope Gmail).",
    )
    args = parser.parse_args()

    token = (os.getenv("E2E_GOOGLE_ACCESS_TOKEN") or "").strip()
    if not token:
        if args.require_token:
            print("ERROR: E2E_GOOGLE_ACCESS_TOKEN is not set.", file=sys.stderr)
            return 1
        print("Skip: E2E_GOOGLE_ACCESS_TOKEN not set (export it or add to .env).")
        return 0

    expect = (os.getenv("E2E_EXPECT_GOOGLE_EMAIL") or "").strip()
    drive_url = os.getenv("DRIVE_MCP_URL", "http://127.0.0.1:8787/mcp").strip()
    gmail_url = os.getenv("GMAIL_MCP_URL", "http://127.0.0.1:8788/mcp").strip()
    cal_url = os.getenv("CALENDAR_MCP_URL", "https://gcal.mcp.claude.com/mcp").strip()

    steps: list[bool] = []

    if args.gmail_only:
        if args.calendar_create_smoke or args.with_drive_download:
            print("Note: --gmail-only ignores --calendar-create-smoke and --with-drive-download.", file=sys.stderr)
        if expect:
            steps.append(_check_gmail_profile_expectation(token, expect))
            if not steps[-1]:
                return 1
        else:
            ok, email = _gmail_profile_email(token)
            if not ok:
                _fail("gmail profile", email)
                return 1
            _ok("gmail profile", email or "(no email in response)")
        steps.append(_gmail_mcp_list(gmail_url, token))
    else:
        if expect:
            steps.append(_check_email_expectation(token, expect))
            if not steps[-1]:
                return 1
        else:
            ok, email = _userinfo_email(token)
            if not ok:
                _fail("userinfo", email)
                return 1
            _ok("userinfo", email or "(no email in response)")

        steps.append(_drive_mcp_list_files(drive_url, token))
        if args.with_drive_download:
            steps.append(_drive_mcp_get_one_pdf(drive_url, token))
        steps.append(_gmail_mcp_list(gmail_url, token))
        steps.append(_calendar_rest_list(token))
        if args.calendar_create_smoke:
            steps.append(_calendar_mcp_create_smoke(cal_url, token))

    if not all(steps):
        return 1
    print("All executed checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
