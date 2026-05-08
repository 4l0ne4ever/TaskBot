import base64

from app.scheduler.queue_consumer import _extract_drive_raw_content


def test_extract_drive_raw_content_prefers_content_base64() -> None:
    payload = {"content_base64": base64.standard_b64encode(b"%PDF-1.7").decode("ascii")}
    raw = _extract_drive_raw_content(payload)
    assert isinstance(raw, bytes)
    assert raw.startswith(b"%PDF")


def test_extract_drive_raw_content_supports_legacy_text_fields() -> None:
    raw = _extract_drive_raw_content({"content": "plain text"})
    assert raw == "plain text"


def test_extract_drive_raw_content_returns_none_for_invalid_payload() -> None:
    assert _extract_drive_raw_content({"content_base64": "!!!"}) is None
