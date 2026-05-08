from __future__ import annotations

import json
from collections import defaultdict

import httpx
import pytest
import redis as redis_lib

from app.services import observability as obs


class _FakeRedis:
    def __init__(self) -> None:
        self._hash: dict[str, int] = defaultdict(int)
        self._events: list[str] = []

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    def hgetall(self, key: str) -> dict[str, str]:  # noqa: ARG002
        return {k: str(v) for k, v in self._hash.items()}

    def lpush(self, key: str, payload: str) -> None:  # noqa: ARG002
        self._events.insert(0, payload)

    def ltrim(self, key: str, start: int, end: int) -> None:  # noqa: ARG002
        self._events = self._events[start : end + 1]


class _FakePipeline:
    def __init__(self, r: _FakeRedis) -> None:
        self._r = r
        self._ops: list[tuple[str, int]] = []

    def hincrby(self, key: str, field: str, amount: int) -> _FakePipeline:  # noqa: ARG002
        self._ops.append((field, amount))
        return self

    def execute(self) -> None:
        for field, amount in self._ops:
            self._r._hash[field] += amount
        self._ops.clear()


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    r = _FakeRedis()
    monkeypatch.setattr(obs, "_redis_client", lambda: r)
    return r


@pytest.fixture(autouse=True)
def _reset_warned_once() -> None:
    obs._warned_once.clear()
    obs._redis_unavailable = False
    object.__getattribute__(obs.settings, "_overrides").clear()


def test_post_langsmith_counts_http_429(fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(obs.settings, "langsmith_tracing", True)
    monkeypatch.setattr(obs.settings, "langsmith_api_key", "k")

    class _Resp:
        status_code = 429
        text = "rate limited"

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *a) -> None:
            return None

        def post(self, *a, **k) -> _Resp:
            return _Resp()

    monkeypatch.setattr(obs.httpx, "Client", _Client)

    obs._post_langsmith_run({"name": "groq_chat_completion", "id": "x"})

    assert fake_redis._hash["attempts"] == 1
    assert fake_redis._hash["http_error"] == 1
    assert fake_redis._hash["http_429"] == 1
    assert fake_redis._hash.get("success", 0) == 0
    ev = json.loads(fake_redis._events[0])
    assert ev["outcome"] == "http_error"
    assert ev["status_code"] == 429
    assert ev["run_name"] == "groq_chat_completion"


def test_post_langsmith_counts_success(fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(obs.settings, "langsmith_tracing", True)
    monkeypatch.setattr(obs.settings, "langsmith_api_key", "k")

    class _Resp:
        status_code = 202
        text = "accepted"

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *a) -> None:
            return None

        def post(self, *a, **k) -> _Resp:
            return _Resp()

    monkeypatch.setattr(obs.httpx, "Client", _Client)

    obs._post_langsmith_run({"name": "pipeline_run_trace"})

    assert fake_redis._hash["attempts"] == 1
    assert fake_redis._hash["success"] == 1


def test_post_langsmith_counts_transport_timeout(fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(obs.settings, "langsmith_tracing", True)
    monkeypatch.setattr(obs.settings, "langsmith_api_key", "k")

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *a) -> None:
            return None

        def post(self, *a, **k) -> None:
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(obs.httpx, "Client", _Client)

    obs._post_langsmith_run({"name": "groq_chat_completion"})

    assert fake_redis._hash["attempts"] == 1
    assert fake_redis._hash["transport_error"] == 1
    ev = json.loads(fake_redis._events[0])
    assert ev["outcome"] == "transport_error"
    assert ev["detail"] == "timeout"


def test_record_llm_call_persists_eval_context(fake_redis: _FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_TRACE_SAMPLE_ID", "sample-1")
    monkeypatch.setenv("EVAL_RUN_ID", "run-1")
    monkeypatch.setattr(obs, "_post_langsmith_run", lambda _payload: None)

    obs.record_llm_call(
        model="m",
        model_tier="primary",
        latency_ms=12,
        prompt_tokens=3,
        completion_tokens=4,
        total_tokens=7,
        call_context={
            "node_name": "extract_tasks",
            "call_purpose": "extract",
            "retry_attempt": 1,
            "chunk_index": 0,
            "chunk_count": 2,
        },
    )

    row = json.loads(fake_redis._events[0])
    assert row["sample_id"] == "sample-1"
    assert row["eval_run_id"] == "run-1"
    assert row["node_name"] == "extract_tasks"
    assert row["call_purpose"] == "extract"
    assert row["retry_attempt"] == 1
    assert row["chunk_count"] == 2


def test_observability_warns_once_when_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_redis():
        raise redis_lib.ConnectionError("redis down")

    warned: list[tuple[object, ...]] = []
    monkeypatch.setattr(obs, "_redis_client", _raise_redis)
    monkeypatch.setattr(obs.logger, "warning", lambda *args, **kwargs: warned.append(args))
    monkeypatch.setattr(obs, "_post_langsmith_run", lambda _payload: None)

    obs.record_pipeline_error(source_type="gmail", user_id="u1", error="e1")
    obs.record_pipeline_error(source_type="gmail", user_id="u1", error="e2")

    assert len(warned) == 1
