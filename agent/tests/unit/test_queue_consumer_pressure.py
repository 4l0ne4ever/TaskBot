"""Unit tests for ``llm_pressure_snapshot`` — specifically the TPD/RPD path
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
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest


class _FakeRedis:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [json.dumps(r) for r in rows]

    async def lrange(self, _key: str, start: int, end: int) -> list[str]:
        return self._rows[start : end + 1]


@pytest.fixture
def pressure_mod(monkeypatch: pytest.MonkeyPatch):
    import importlib

    return importlib.import_module("app.scheduler.pressure")


def _patch_redis(monkeypatch: pytest.MonkeyPatch, module, rows: list[dict]) -> None:
    async def _fake() -> _FakeRedis:
        return _FakeRedis(rows)

    monkeypatch.setattr(module, "get_redis", _fake)


def test_pressure_empty_window_is_healthy(pressure_mod, monkeypatch):
    _patch_redis(monkeypatch, pressure_mod, [])
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert high is False
    assert ratio == 0.0
    assert sample == 0
    assert daily is False


def test_pressure_majority_tpd_triggers_daily_exhausted(pressure_mod, monkeypatch):
    rows = [
        {
            "model": "primary",
            "error": "429 tokens per day (TPD): Limit 1, Used 1. try again in 845s",
            "rate_limit_kind": "tpd",
        }
    ] * 20
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert high is True
    assert ratio == 1.0
    assert sample == 20
    assert daily is True, "majority-TPD window must flag daily_quota_exhausted"


def test_pressure_tpm_only_does_not_flag_daily(pressure_mod, monkeypatch):
    rows = [
        {"model": "p", "error": "429 tokens per minute (TPM)", "rate_limit_kind": "tpm"}
    ] * 20
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert high is True
    assert daily is False, "TPM window must NOT flag daily_quota_exhausted"


def test_pressure_mixed_window_falls_back_to_majority_rule(pressure_mod, monkeypatch):
    rows = (
        [{"model": "p", "error": "429 TPM", "rate_limit_kind": "tpm"}] * 6
        + [{"model": "p", "error": "429 TPD", "rate_limit_kind": "tpd"}] * 4
        + [{"model": "p", "error": None}] * 10
    )
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert ratio == 0.5, "10 of 20 are rate-limited"
    assert high is True
    assert daily is False, "only 4/10 rate-limited are daily; not majority"


def test_pressure_tiny_sample_never_flags_daily(pressure_mod, monkeypatch):
    # Threshold protects against a single stale TPD row freezing ingestion.
    rows = [{"model": "p", "error": "429 TPD", "rate_limit_kind": "tpd"}] * 2
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert daily is False


def _yesterday_ts() -> str:
    return (datetime.now(UTC) - timedelta(days=1)).isoformat()


def _today_ts() -> str:
    return datetime.now(UTC).isoformat()


def test_pressure_stale_tpd_from_yesterday_is_ignored(pressure_mod, monkeypatch):
    """Core regression: TPD errors from a previous UTC day must NOT block today's
    syncs. Groq quota resets at UTC midnight — old-day errors in ``obs:llm:calls``
    are irrelevant and must be skipped."""
    rows = [
        {
            "ts": _yesterday_ts(),
            "model": "primary",
            "error": "429 tokens per day (TPD): try again in 845s",
            "rate_limit_kind": "tpd",
        }
    ] * 20
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert sample == 0, "all entries are from yesterday → zero valid entries today"
    assert high is False
    assert daily is False, "stale TPD entries must not block today's syncs"


def test_pressure_mixed_stale_and_fresh_only_counts_today(pressure_mod, monkeypatch):
    """Yesterday's TPD errors + today's clean calls → healthy (only today's window counted)."""
    rows = (
        # 20 today's entries, no errors
        [{"ts": _today_ts(), "model": "p", "error": None}] * 20
        # 20 yesterday's TPD entries — should be invisible
        + [{"ts": _yesterday_ts(), "model": "p", "error": "429 TPD", "rate_limit_kind": "tpd"}] * 20
    )
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert ratio == 0.0, "only today's clean calls should be counted"
    assert high is False
    assert daily is False


def test_pressure_today_tpd_still_triggers(pressure_mod, monkeypatch):
    """TPD errors from today still correctly flag daily_quota_exhausted."""
    rows = [
        {
            "ts": _today_ts(),
            "model": "primary",
            "error": "429 tokens per day (TPD): try again in 845s",
            "rate_limit_kind": "tpd",
        }
    ] * 20
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert high is True
    assert daily is True, "today's TPD majority must still flag exhausted"


def test_pressure_no_ts_field_included_conservatively(pressure_mod, monkeypatch):
    """Entries without a ``ts`` field are included in the window (conservative).
    This preserves backward compatibility for any entries written before the
    timestamp field was added."""
    rows = [
        {"model": "primary", "error": "429 tokens per day (TPD)", "rate_limit_kind": "tpd"}
    ] * 20
    _patch_redis(monkeypatch, pressure_mod, rows)
    high, ratio, sample, daily = asyncio.run(pressure_mod.llm_pressure_snapshot())
    assert sample == 20
    assert daily is True, "ts-less entries are included conservatively"
