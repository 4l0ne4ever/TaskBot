import hashlib
from html.parser import HTMLParser
from io import BytesIO

import fitz
from docx import Document


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self._parts.append(value)

    def text(self) -> str:
        return "\n".join(self._parts)


def parse_email_html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html or "")
    parser.close()
    return parser.text()


def parse_pdf_bytes_to_text(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        pages = [page.get_text("text").strip() for page in doc]
    return "\n".join([p for p in pages if p])


def parse_docx_bytes_to_text(file_bytes: bytes) -> str:
    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)


def compute_content_hash(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()
