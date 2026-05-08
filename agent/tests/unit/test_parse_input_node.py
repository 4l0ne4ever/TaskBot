from app.pipeline.nodes.parse_input import CHUNK_CHAR_LIMIT, GMAIL_PROFILE_CHAR_LIMITS, parse_input


def test_parse_input_gmail_extracts_metadata_and_text() -> None:
    result = parse_input(
        {
            "source_type": "gmail",
            "raw_content": "<p>Hello world</p>",
            "metadata": {
                "sender": "a@b.com",
                "sent_at": "2026-04-01T10:00:00Z",
                "subject": "Hello",
            },
            "errors": [],
        }
    )
    assert result["should_stop"] is False
    assert "Hello world" in result["cleaned_text"]
    assert result["metadata"]["sender"] == "a@b.com"
    assert result["metadata"]["subject"] == "Hello"


def test_parse_input_chunks_long_gmail_text() -> None:
    long_text = "a" * (CHUNK_CHAR_LIMIT + 10)
    result = parse_input(
        {
            "source_type": "gmail",
            "raw_content": long_text,
            "metadata": {},
            "errors": [],
        }
    )
    assert result["should_stop"] is False
    cap = GMAIL_PROFILE_CHAR_LIMITS["balanced"]
    assert len(result["cleaned_text"]) == cap
    assert len(result["chunks"]) == 1
    assert len(result["chunks"][0]) == cap
    assert result["cleaned_text"] == result["chunks"][0]


def test_parse_input_respects_sync_profile_char_limit() -> None:
    long_text = "a" * (CHUNK_CHAR_LIMIT + 10)
    result = parse_input(
        {
            "source_type": "gmail",
            "raw_content": long_text,
            "metadata": {"sync_profile": "broad"},
            "errors": [],
        }
    )
    assert result["should_stop"] is False
    cap = GMAIL_PROFILE_CHAR_LIMITS["broad"]
    assert len(result["cleaned_text"]) == cap
    assert result["metadata"]["sync_profile"] == "broad"


def test_parse_input_stops_on_invalid_upload_raw_content() -> None:
    result = parse_input(
        {
            "source_type": "upload",
            "raw_content": "not-bytes",
            "metadata": {"file_name": "x.pdf"},
            "errors": [],
        }
    )
    assert result["should_stop"] is True
    assert result["cleaned_text"] == ""
    assert result["chunks"] == []
    assert result["errors"]
