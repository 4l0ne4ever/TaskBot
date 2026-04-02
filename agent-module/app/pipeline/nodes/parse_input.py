from app.pipeline.parsers import (
    parse_docx_bytes_to_text,
    parse_email_html_to_text,
    parse_pdf_bytes_to_text,
)
from app.pipeline.state import PipelineState

CHUNK_CHAR_LIMIT = 32000


def _extract_metadata(metadata: dict | None) -> dict:
    metadata = metadata or {}
    return {
        "sender": metadata.get("sender"),
        "sent_at": metadata.get("sent_at"),
        "subject": metadata.get("subject"),
        "file_name": metadata.get("file_name"),
    }


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
    raw_content = state.get("raw_content")
    source_type = state.get("source_type")
    metadata = _extract_metadata(state.get("metadata") if isinstance(state.get("metadata"), dict) else None)

    try:
        if source_type == "gmail":
            cleaned_text = parse_email_html_to_text(_extract_gmail_html(raw_content))
        elif source_type in {"drive", "upload"}:
            if not isinstance(raw_content, (bytes, bytearray)):
                raise ValueError("Expected bytes content for drive/upload source")

            filename = str(metadata.get("file_name") or "").lower()
            if filename.endswith(".docx"):
                cleaned_text = parse_docx_bytes_to_text(bytes(raw_content))
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
            "should_stop": False,
        }
    except Exception as exc:
        errors.append(f"parse_input failed: {exc}")
        return {
            "cleaned_text": "",
            "chunks": [],
            "metadata": metadata,
            "errors": errors,
            "should_stop": True,
        }
