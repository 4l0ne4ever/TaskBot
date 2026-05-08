from datetime import date

from app.pipeline.parsers import (
    parse_docx_bytes_to_text,
    parse_email_html_to_text,
    parse_pdf_bytes_to_text,
)
from app.pipeline.policy import get_pipeline_policy
from app.pipeline.state import PipelineState

_WEEKDAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEKDAY_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

CHUNK_CHAR_LIMIT = 32000
GMAIL_PROFILE_CHAR_LIMITS = {
    "strict_work": 8000,
    "balanced": 12000,
    "broad": 20000,
}


def _enrich_sent_at(raw: str | None) -> str | None:
    """Append day-of-week to a date string so LLM can resolve relative weekday references."""
    if not raw:
        return raw
    date_part = str(raw)[:10]
    try:
        d = date.fromisoformat(date_part)
    except ValueError:
        return raw
    dow_en = _WEEKDAY_EN[d.weekday()]
    dow_vi = _WEEKDAY_VI[d.weekday()]
    return f"{date_part} ({dow_en} / {dow_vi})"


def _extract_metadata(metadata: dict | None) -> dict:
    metadata = metadata or {}
    out = dict(metadata)
    out["sent_at"] = _enrich_sent_at(metadata.get("sent_at"))
    return out


def _chunk_text(text: str, chunk_size: int = CHUNK_CHAR_LIMIT) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _extract_gmail_html(raw_content: str | bytes | dict | None) -> str:
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, dict):
        html = raw_content.get("html")
        if isinstance(html, str):
            return html
        body = raw_content.get("body")
        if isinstance(body, str):
            return body
    return ""


def parse_input(state: PipelineState) -> dict:
    errors = list(state.get("errors", []))
    policy_version = get_pipeline_policy().version
    raw_content = state.get("raw_content")
    source_type = state.get("source_type")
    metadata = _extract_metadata(state.get("metadata") if isinstance(state.get("metadata"), dict) else None)

    try:
        if source_type == "gmail":
            cleaned_text = parse_email_html_to_text(_extract_gmail_html(raw_content))
            profile = str(metadata.get("sync_profile") or "balanced")
            profile_limit = GMAIL_PROFILE_CHAR_LIMITS.get(profile, GMAIL_PROFILE_CHAR_LIMITS["balanced"])
            if len(cleaned_text) > profile_limit:
                cleaned_text = cleaned_text[:profile_limit]
        elif source_type in {"drive", "upload"}:
            if not isinstance(raw_content, (bytes, bytearray)):
                raise ValueError("Expected bytes content for drive/upload source")

            filename = str(metadata.get("file_name") or "").lower()
            if filename.endswith(".docx"):
                cleaned_text = parse_docx_bytes_to_text(bytes(raw_content))
            elif filename.endswith((".html", ".htm", ".txt", ".md")):
                cleaned_text = parse_email_html_to_text(bytes(raw_content).decode("utf-8", errors="replace"))
            else:
                cleaned_text = parse_pdf_bytes_to_text(bytes(raw_content))
        else:
            raise ValueError(f"Unsupported source_type: {source_type}")

        if not cleaned_text.strip():
            raise ValueError("Parsed content is empty")

        chunks = _chunk_text(cleaned_text)
        return {
            "cleaned_text": chunks[0],
            "chunks": chunks,
            "metadata": metadata,
            "policy_version": policy_version,
            "should_stop": False,
        }
    except Exception as exc:
        errors.append(f"parse_input failed: {exc}")
        return {
            "cleaned_text": "",
            "chunks": [],
            "metadata": metadata,
            "policy_version": policy_version,
            "errors": errors,
            "should_stop": True,
        }
