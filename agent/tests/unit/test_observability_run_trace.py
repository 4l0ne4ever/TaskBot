"""Unit tests for ``record_pipeline_run_trace`` — specifically the fix that
the ``obs:pipeline:runs`` row carries honest model-fallback provenance
instead of sniffing error strings.

Background: production Redis showed 74% of real LLM calls routing to the
8B fallback model while every single pipeline run recorded
``fallback_used=False``. That flag only checked for a "normalize_tasks
failed" error string and never reflected actual model routing. The new
row adds ``llm_fallback_used`` (from per-call provenance) and renames the
old semantics to ``normalize_fallback_used`` while keeping ``fallback_used``
as a back-compat alias.
"""

from __future__ import annotations

import json

import pytest

from app.services import observability as obs


class _CapturingRedis:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def lpush(self, key: str, payload: str) -> None:  # noqa: ARG002
        try:
            self.rows.append(json.loads(payload))
        except Exception:
            self.rows.append({"_raw": payload})

    def ltrim(self, *_a, **_k) -> None:
        return None


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> _CapturingRedis:
    c = _CapturingRedis()
    monkeypatch.setattr(obs, "_redis_client", lambda: c)
    return c


@pytest.fixture(autouse=True)
def _reset_warned_once() -> None:
    obs._warned_once.clear()
    obs._redis_unavailable = False


def _task() -> dict:
    return {
        "title": "X",
        "decision_band": "accept",
        "deadline_v2": {"type": "none"},
        "uncertainty": None,
    }


def test_record_run_trace_reflects_llm_fallback_when_provided(
    captured: _CapturingRedis,
) -> None:
    state = {"source_type": "gmail", "user_id": "u1", "source_doc_id": "d1", "errors": []}
    summary = {
        "llm_calls_total": 4,
        "llm_fallback_calls": 2,
        "llm_fallback_used": True,
        "llm_rate_limited_calls": 1,
        "llm_models": ["primary", "primary", "fallback", "fallback"],
    }

    obs.record_pipeline_run_trace(
        state, [_task()], "v2", provenance_summary=summary
    )

    assert len(captured.rows) == 1
    row = captured.rows[0]
    assert row["llm_fallback_used"] is True
    assert row["llm_fallback_calls"] == 2
    assert row["llm_calls_total"] == 4
    assert row["llm_rate_limited_calls"] == 1
    assert row["llm_models"] == ["primary", "primary", "fallback", "fallback"]
    assert row["normalize_fallback_used"] is False
    assert row["fallback_used"] is False


def test_record_run_trace_without_provenance_does_not_fabricate_llm_flag(
    captured: _CapturingRedis,
) -> None:
    state = {"source_type": "upload", "user_id": "u", "errors": []}

    obs.record_pipeline_run_trace(state, [_task()], "v2")

    row = captured.rows[0]
    assert row["llm_fallback_used"] is False
    assert row["llm_calls_total"] == 0
    assert row["llm_fallback_calls"] == 0
    assert row["llm_models"] == []


def test_record_run_trace_does_not_nameerror_when_langsmith_enabled(
    captured: _CapturingRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a stray ``fallback_used`` reference in the LangSmith
    payload caused a NameError every time tracing was on. The Redis row
    succeeded but the function then raised, propagating out of validate_tasks
    and failing every production pipeline run. Pin that the function returns
    cleanly even with tracing enabled.
    """

    monkeypatch.setattr(obs.settings, "langsmith_tracing", True)
    monkeypatch.setattr(obs.settings, "langsmith_api_key", "test-key")

    posted: list[dict] = []
    monkeypatch.setattr(obs, "_post_langsmith_run", lambda payload: posted.append(payload))

    state = {"source_type": "gmail", "user_id": "u", "errors": []}
    obs.record_pipeline_run_trace(
        state,
        [_task()],
        "v2",
        provenance_summary={
            "llm_calls_total": 2,
            "llm_fallback_calls": 1,
            "llm_fallback_used": True,
            "llm_rate_limited_calls": 1,
            "llm_models": ["primary", "fallback"],
        },
    )

    assert len(captured.rows) == 1
    chain_runs = [p for p in posted if p.get("run_type") == "chain"]
    assert chain_runs, "expected at least one chain run posted to LangSmith"
    out = chain_runs[-1]["outputs"]
    assert out["normalize_fallback_used"] is False
    assert out["llm_fallback_used"] is True
    assert out["llm_fallback_calls"] == 1
    assert out["llm_rate_limited_calls"] == 1


def test_record_run_trace_preserves_normalize_fallback_semantics(
    captured: _CapturingRedis,
) -> None:
    state = {
        "source_type": "gmail",
        "user_id": "u",
        "errors": ["normalize_tasks failed: KeyError('title')"],
    }

    obs.record_pipeline_run_trace(state, [_task()], "v2")

    row = captured.rows[0]
    assert row["normalize_fallback_used"] is True
    assert row["fallback_used"] is True
    assert row["llm_fallback_used"] is False


def test_record_run_trace_still_posts_langsmith_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(obs, "_redis_client", _raise_redis)
    monkeypatch.setattr(obs.settings, "langsmith_tracing", True)
    monkeypatch.setattr(obs.settings, "langsmith_api_key", "test-key")

    posted: list[dict] = []
    monkeypatch.setattr(obs, "_post_langsmith_run", lambda payload: posted.append(payload))

    state = {"source_type": "gmail", "user_id": "u", "errors": []}
    obs.record_pipeline_run_trace(
        state,
        [_task()],
        "v2",
        provenance_summary={
            "llm_calls_total": 1,
            "llm_fallback_calls": 0,
            "llm_fallback_used": False,
            "llm_rate_limited_calls": 0,
            "llm_models": ["primary"],
        },
    )

    chain_runs = [p for p in posted if p.get("run_type") == "chain"]
    assert chain_runs, "expected LangSmith chain payload even when Redis is down"
