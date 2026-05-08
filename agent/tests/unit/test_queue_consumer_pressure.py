"""Unit tests for ``_llm_pressure_snapshot`` — specifically the TPD/RPD path
added in pass 6 to stop requeuing jobs that will deterministically fail until
the next UTC day boundary.

Background: before this fix, a daily-window rate limit on Groq would trip the
pressure signal, defer the job, and trigger a 45s requeue that immediately
hit the same quota again — up to ``llm_pressure_requeue_max_retries`` wasted
round-trips per sync. The new contract: when the sample is majority-daily,
return ``daily_quota_exhausted=True`` so callers can short-circuit the whole
sync instead of churning.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


class _FakeRedis:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [json.dumps(r) for r in rows]

    async def lrange(self, _key: str, start: int, end: int) -> list[str]:
        return self._rows[start : end + 1]


@pytest.fixture
def queue_consumer(monkeypatch: pytest.MonkeyPatch):
    import importlib

    mod = importlib.import_module("app.scheduler.queue_consumer")
    return mod


def _patch_redis(monkeypatch: pytest.MonkeyPatch, module, rows: list[dict]) -> None:
    async def _fake() -> _FakeRedis:
        return _FakeRedis(rows)

    monkeypatch.setattr(module, "_get_redis", _fake)


def test_pressure_empty_window_is_healthy(queue_consumer, monkeypatch):
    _patch_redis(monkeypatch, queue_consumer, [])
    high, ratio, sample, daily = asyncio.run(queue_consumer._llm_pressure_snapshot())
    assert high is False
    assert ratio == 0.0
    assert sample == 0
    assert daily is False


def test_pressure_majority_tpd_triggers_daily_exhausted(queue_consumer, monkeypatch):
    rows = [
        {
            "model": "primary",
            "error": "429 tokens per day (TPD): Limit 1, Used 1. try again in 845s",
            "rate_limit_kind": "tpd",
        }
    ] * 20
    _patch_redis(monkeypatch, queue_consumer, rows)
    high, ratio, sample, daily = asyncio.run(queue_consumer._llm_pressure_snapshot())
    assert high is True
    assert ratio == 1.0
    assert sample == 20
    assert daily is True, "majority-TPD window must flag daily_quota_exhausted"


def test_pressure_tpm_only_does_not_flag_daily(queue_consumer, monkeypatch):
    rows = [
        {"model": "p", "error": "429 tokens per minute (TPM)", "rate_limit_kind": "tpm"}
    ] * 20
    _patch_redis(monkeypatch, queue_consumer, rows)
    high, ratio, sample, daily = asyncio.run(queue_consumer._llm_pressure_snapshot())
    assert high is True
    assert daily is False, "TPM window must NOT flag daily_quota_exhausted"


def test_pressure_mixed_window_falls_back_to_majority_rule(queue_consumer, monkeypatch):
    rows = (
        [{"model": "p", "error": "429 TPM", "rate_limit_kind": "tpm"}] * 6
        + [{"model": "p", "error": "429 TPD", "rate_limit_kind": "tpd"}] * 4
        + [{"model": "p", "error": None}] * 10
    )
    _patch_redis(monkeypatch, queue_consumer, rows)
    high, ratio, sample, daily = asyncio.run(queue_consumer._llm_pressure_snapshot())
    assert ratio == 0.5, "10 of 20 are rate-limited"
    assert high is True
    assert daily is False, "only 4/10 rate-limited are daily; not majority"


def test_pressure_tiny_sample_never_flags_daily(queue_consumer, monkeypatch):
    # Threshold protects against a single stale TPD row freezing ingestion.
    rows = [{"model": "p", "error": "429 TPD", "rate_limit_kind": "tpd"}] * 2
    _patch_redis(monkeypatch, queue_consumer, rows)
    high, ratio, sample, daily = asyncio.run(queue_consumer._llm_pressure_snapshot())
    assert daily is False
