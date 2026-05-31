"""Unit tests for the upload-pipeline handler (Round 12, 2026-05-30).

Pre-Round-12 the queue consumer had no ``elif source == "upload"`` branch
and rejected upload jobs at the ``if not user_id or not token`` guard
(uploads carry no OAuth token). The handler added here fetches the file
from S3, runs it through the LangGraph pipeline, and updates
``upload:status:*`` so the frontend's polling can advance through
``queued → extracting → done``. See ``tests/e2e/real-world-validation.md``
§7.14 for the pre-Round-12 forensic.

These tests stub S3 + the pipeline invocation so they run offline with no
AWS creds and no LLM call — they cover the wiring (status transitions,
field validation, fail-path), not the pipeline itself (which has its own
``test_pipeline_upload.py``).
"""
from __future__ import annotations

import asyncio

import pytest

from app.scheduler.processors import upload as upload_mod

_USER_ID = "11111111-1111-1111-1111-111111111111"
_DOC_ID = "22222222-2222-2222-2222-222222222222"
_UPLOAD_ID = "upload-abc-123"


@pytest.fixture
def stubs(monkeypatch):
    """Stub S3, AsyncSessionLocal, pipeline, and status writer so the
    handler exercises its own logic without external dependencies."""
    captured = {"statuses": [], "fetched": False, "invoked": False, "session_used": False}

    # The status writer is inlined inside ``process_upload_job`` and uses
    # ``get_redis()``; we intercept by stubbing the redis client itself.
    class _FakeRedis:
        async def set(self, key, value):
            # Key format: "upload:status:<upload_id>"
            uid = key.rsplit(":", 1)[-1]
            captured["statuses"].append((uid, value))
    async def fake_get_redis(): return _FakeRedis()
    monkeypatch.setattr(upload_mod, "get_redis", fake_get_redis)

    # Stub boto3.client → an object whose get_object returns 5 bytes.
    class _Body:
        def read(self):
            captured["fetched"] = True
            return b"%PDF-"

    class _S3:
        def get_object(self, **kw):
            return {"Body": _Body()}

    monkeypatch.setattr("boto3.client", lambda *a, **kw: _S3())

    # Pretend AWS is configured.
    monkeypatch.setattr(upload_mod.settings, "aws_s3_bucket", "test-bucket", raising=False)
    monkeypatch.setattr(upload_mod.settings, "aws_region", "us-east-1", raising=False)
    monkeypatch.setattr(upload_mod.settings, "aws_access_key_id", "x", raising=False)
    monkeypatch.setattr(upload_mod.settings, "aws_secret_access_key", "y", raising=False)

    # Stub the DB session helper — handler only uses it to insert a PipelineRun.
    class _FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return False
        def add(self, *a, **kw): captured["session_used"] = True
        async def flush(self): pass
        def begin(self): return _FakeBegin()
    class _FakeBegin:
        async def __aenter__(self): return None
        async def __aexit__(self, *exc): return False
    monkeypatch.setattr(upload_mod, "AsyncSessionLocal", _FakeSession)

    # Stub the pipeline invocation.
    async def fake_invoke(state):
        captured["invoked"] = True
        captured["state"] = state
        return state
    monkeypatch.setattr(upload_mod, "invoke_pipeline", fake_invoke)

    # Stub mark_run_failed (only used on error path).
    async def fake_mark_failed(*a, **kw): pass
    monkeypatch.setattr(upload_mod, "mark_run_failed", fake_mark_failed)

    return captured


def test_upload_happy_path_flips_status_extracting_then_done(stubs):
    asyncio.run(upload_mod.process_upload_job(
        _USER_ID,
        source_doc_id=_DOC_ID, s3_key="path/to/x.pdf", file_name="x.pdf", upload_id=_UPLOAD_ID,
    ))
    assert stubs["fetched"] is True
    assert stubs["invoked"] is True
    statuses = [s for (uid, s) in stubs["statuses"] if uid == _UPLOAD_ID]
    assert statuses == ["extracting", "done"], f"got {statuses}"


def test_upload_state_carries_bytes_and_filename_to_pipeline(stubs):
    asyncio.run(upload_mod.process_upload_job(
        _USER_ID,
        source_doc_id=_DOC_ID, s3_key="x.pdf", file_name="report.pdf", upload_id=_UPLOAD_ID,
    ))
    state = stubs["state"]
    assert state["source_type"] == "upload"
    assert state["raw_content"] == b"%PDF-"
    assert state["metadata"]["file_name"] == "report.pdf"
    assert state["metadata"]["upload_id"] == _UPLOAD_ID
    assert state["user_id"] == _USER_ID
    assert "access_token" not in state  # uploads have no token


def test_upload_failure_flips_status_to_failed(stubs, monkeypatch):
    async def boom(state):
        raise RuntimeError("PDF parse failed")
    monkeypatch.setattr(upload_mod, "invoke_pipeline", boom)
    with pytest.raises(RuntimeError, match="PDF parse failed"):
        asyncio.run(upload_mod.process_upload_job(
            _USER_ID,
            source_doc_id=_DOC_ID, s3_key="x.pdf", file_name="x.pdf", upload_id=_UPLOAD_ID,
        ))
    statuses = [s for (uid, s) in stubs["statuses"] if uid == _UPLOAD_ID]
    # First "extracting", then "failed" — the UI sees something honest
    # instead of an eternal spinner.
    assert statuses[-1] == "failed"


def test_upload_raises_when_aws_not_configured(stubs, monkeypatch):
    monkeypatch.setattr(upload_mod.settings, "aws_s3_bucket", None, raising=False)
    with pytest.raises(RuntimeError, match="AWS S3 not configured"):
        asyncio.run(upload_mod.process_upload_job(
            _USER_ID,
            source_doc_id=_DOC_ID, s3_key="x.pdf", file_name="x.pdf", upload_id=_UPLOAD_ID,
        ))
    # Even an early config failure must surface to the UI.
    statuses = [s for (uid, s) in stubs["statuses"] if uid == _UPLOAD_ID]
    assert "failed" in statuses
