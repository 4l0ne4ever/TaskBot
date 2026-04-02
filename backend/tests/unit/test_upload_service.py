import pytest

from app.services.upload_service import (
    build_s3_key,
    compute_content_hash,
    ensure_supported_file,
    upload_bytes_to_s3,
)


def test_ensure_supported_file_accepts_pdf_docx() -> None:
    ensure_supported_file("a.pdf")
    ensure_supported_file("b.docx")


def test_ensure_supported_file_rejects_other_extension() -> None:
    with pytest.raises(ValueError):
        ensure_supported_file("a.txt")


def test_compute_content_hash_deterministic() -> None:
    assert compute_content_hash(b"abc") == compute_content_hash(b"abc")


def test_build_s3_key() -> None:
    from uuid import UUID

    key = build_s3_key(UUID("11111111-1111-1111-1111-111111111111"), "upload-1", "x.pdf")
    assert key == "11111111-1111-1111-1111-111111111111/upload-1.pdf"


def test_upload_bytes_to_s3_calls_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    class _FakeClient:
        def put_object(self, **kwargs):
            called.update(kwargs)

    def _fake_boto3_client(*args, **kwargs):
        return _FakeClient()

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdHRlc3R0ZXN0dGVzdHRlc3R0ZXN0dGVzdD0=")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "x")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/x")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket-test")

    monkeypatch.setattr("app.services.upload_service.boto3.client", _fake_boto3_client)
    upload_bytes_to_s3(s3_key="k", content=b"abc", content_type="application/pdf")
    assert called["Bucket"] == "taskbot-uploads-test"
    assert called["Key"] == "k"
