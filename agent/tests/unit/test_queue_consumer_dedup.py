"""Tests for source-document idempotency in the queue consumer.

Forensic pass 5 (2026-04-18) found that the same Gmail message could be
ingested dozens of times for the same user (one hash → 91 rows in
production). The queue consumer now delegates the duplicate-detection
step to :func:`app.scheduler.queue_consumer._find_existing_source_doc`
and these tests cover the three behaviours the caller relies on:

1. Returning an existing row so the caller can short-circuit the
   pipeline when ``processed_at`` is already populated.
2. Returning ``None`` when the triple is new so a fresh row is inserted.
3. Defensively returning ``None`` when ``source_ref`` is missing, which
   keeps the helper safe to call even before validation of upstream MCP
   payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scheduler.queue_consumer import _find_existing_source_doc


def _mock_session_returning(result):
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=result)
    session = MagicMock()
    session.execute = AsyncMock(return_value=exec_result)
    return session


@pytest.mark.asyncio
async def test_find_existing_source_doc_returns_row_when_present() -> None:
    uid = uuid.uuid4()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        processed_at=datetime.now(timezone.utc),
    )
    session = _mock_session_returning(existing)

    found = await _find_existing_source_doc(
        session,
        user_id=uid,
        source_type="gmail",
        source_ref="msg-123",
    )

    assert found is existing
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_find_existing_source_doc_returns_none_for_new_ref() -> None:
    session = _mock_session_returning(None)

    found = await _find_existing_source_doc(
        session,
        user_id=uuid.uuid4(),
        source_type="drive",
        source_ref="file-abc",
    )

    assert found is None
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_find_existing_source_doc_skips_lookup_when_ref_blank() -> None:
    session = _mock_session_returning(object())

    found = await _find_existing_source_doc(
        session,
        user_id=uuid.uuid4(),
        source_type="gmail",
        source_ref="",
    )

    assert found is None
    assert session.execute.await_count == 0
