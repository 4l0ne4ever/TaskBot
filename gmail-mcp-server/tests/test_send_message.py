"""Unit test for the Gmail MCP send_message MIME builder (Phase 8.3)."""
from __future__ import annotations

import base64
from email import message_from_bytes

from app.main import _build_raw_message


def _decode(raw: str):
    # Gmail's raw field is base64url without padding requirements; pad to decode.
    padded = raw + "=" * (-len(raw) % 4)
    return message_from_bytes(base64.urlsafe_b64decode(padded))


def test_build_raw_message_sets_headers_and_parts() -> None:
    raw = _build_raw_message(
        to="anna@example.com",
        subject="Weekly Brief",
        body_html="<b>hello</b>",
        body_text="hello",
    )
    msg = _decode(raw)
    assert msg["To"] == "anna@example.com"
    assert msg["Subject"] == "Weekly Brief"
    assert msg.is_multipart()
    types = {p.get_content_type() for p in msg.walk() if not p.is_multipart()}
    assert "text/plain" in types
    assert "text/html" in types


def test_build_raw_message_omits_from_when_no_sender() -> None:
    raw = _build_raw_message(to="a@b.com", subject="s", body_html="<p>x</p>")
    msg = _decode(raw)
    assert msg["From"] is None  # Gmail uses the authenticated account


def test_build_raw_message_sets_from_when_sender_given() -> None:
    raw = _build_raw_message(to="a@b.com", subject="s", body_html="<p>x</p>", sender="me@example.com")
    msg = _decode(raw)
    assert "me@example.com" in (msg["From"] or "")
