"""Tests for the Cerebras-only strict-primary path (production quality-first
mode + eval pinned mode share the same code path).

Covered:

- ``LLM_STRICT_PRIMARY=cerebras`` activates the path (preferred name).
- Legacy ``EVAL_CEREBRAS_ONLY=1`` still activates it (backward compat).
- Transient 429 (TPM/RPM) → retried with backoff, eventually succeeds.
- Daily 429 (TPD/RPD) → raised immediately without retry (would be wasted).
- Non-rate-limit exception → raised immediately (no retry path can help).
- All retries exhausted on transient → last exception raised.
- Provenance is recorded once per call with ``rate_limited`` reflecting whether
  any attempt saw a 429.
- No fallback is ever invoked from this path (no Groq/Gemini calls).
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def llm(monkeypatch):
    """Reload llm module with patched primitives so each test starts clean."""
    import app.pipeline.llm as mod

    # Reset module-level state that may leak across tests.
    mod._CEREBRAS_STRICT_DEPRECATION_WARNED = False
    mod.reset_circuit_for_tests()
    # Make sure both env var paths start unset.
    monkeypatch.delenv("LLM_STRICT_PRIMARY", raising=False)
    monkeypatch.delenv("EVAL_CEREBRAS_ONLY", raising=False)
    # Never actually call the Cerebras client.
    monkeypatch.setattr(mod, "_get_cerebras_client", lambda: object())
    # Pretend Cerebras is configured (would otherwise short-circuit).
    monkeypatch.setattr(mod, "_cerebras_configured", lambda: True)
    # Make sleep instantaneous so the test doesn't actually wait 7 seconds.
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    return mod


def _make_rate_limit_exc(message: str) -> Exception:
    return RuntimeError(f"429 {message}")


def test_strict_mode_activated_by_new_env(llm, monkeypatch):
    monkeypatch.setenv("LLM_STRICT_PRIMARY", "cerebras")
    assert llm._cerebras_only() is True


def test_strict_mode_activated_by_legacy_env_for_backward_compat(llm, monkeypatch, caplog):
    monkeypatch.setenv("EVAL_CEREBRAS_ONLY", "1")
    with caplog.at_level("WARNING", logger="app.pipeline.llm"):
        assert llm._cerebras_only() is True
    assert any("EVAL_CEREBRAS_ONLY is deprecated" in r.message for r in caplog.records)


def test_strict_mode_off_by_default(llm):
    assert llm._cerebras_only() is False


def test_new_env_present_suppresses_deprecation_warning(llm, monkeypatch, caplog):
    monkeypatch.setenv("LLM_STRICT_PRIMARY", "cerebras")
    monkeypatch.setenv("EVAL_CEREBRAS_ONLY", "1")
    with caplog.at_level("WARNING", logger="app.pipeline.llm"):
        assert llm._cerebras_only() is True
    assert not any("deprecated" in r.message for r in caplog.records)


def test_strict_success_on_first_attempt_records_clean_provenance(llm, monkeypatch):
    monkeypatch.setattr(llm, "_create", lambda *a, **k: "task-json")
    with llm.collect_provenance() as records:
        out = llm._call_cerebras_strict("p", 0.0, system_prompt="s", max_tokens=None)
    assert out == "task-json"
    assert len(records) == 1
    assert records[0].model == llm.settings.cerebras_model
    assert records[0].is_fallback is False
    assert records[0].rate_limited is False


def test_strict_retries_on_transient_tpm_then_succeeds(llm, monkeypatch):
    """TPM is a transient bucket — backoff and try again."""
    calls = {"n": 0}

    def fake_create(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _make_rate_limit_exc("rate_limit_exceeded on tokens per minute (TPM)")
        return "ok"

    monkeypatch.setattr(llm, "_create", fake_create)
    with llm.collect_provenance() as records:
        out = llm._call_cerebras_strict("p", 0.0, system_prompt="s", max_tokens=None)
    assert out == "ok"
    assert calls["n"] == 3
    assert len(records) == 1
    # Eventual success but at least one attempt saw 429 → rate_limited=True.
    assert records[0].rate_limited is True
    assert records[0].is_fallback is False


def test_strict_does_not_retry_on_daily_quota(llm, monkeypatch):
    """TPD/RPD reset only at next UTC day — retrying in-process is wasted."""
    calls = {"n": 0}

    def fake_create(*a, **k):
        calls["n"] += 1
        raise _make_rate_limit_exc("rate_limit_exceeded on tokens per day (TPD); try again in 3600s")

    monkeypatch.setattr(llm, "_create", fake_create)
    with llm.collect_provenance() as records:
        with pytest.raises(RuntimeError, match="TPD"):
            llm._call_cerebras_strict("p", 0.0, system_prompt="s", max_tokens=None)
    # Single attempt — no retry.
    assert calls["n"] == 1
    assert records[0].rate_limited is True


def test_strict_raises_immediately_on_non_rate_limit_error(llm, monkeypatch):
    """A 500 / network error has no retry path that could plausibly help."""
    calls = {"n": 0}

    def fake_create(*a, **k):
        calls["n"] += 1
        raise RuntimeError("connection reset by peer")

    monkeypatch.setattr(llm, "_create", fake_create)
    with pytest.raises(RuntimeError, match="connection reset"):
        llm._call_cerebras_strict("p", 0.0, system_prompt="s", max_tokens=None)
    assert calls["n"] == 1


def test_strict_raises_last_exception_after_retry_exhaustion(llm, monkeypatch):
    """4 attempts (1 immediate + 3 retries) on transient → last 429 propagates."""
    calls = {"n": 0}

    def fake_create(*a, **k):
        calls["n"] += 1
        raise _make_rate_limit_exc(f"TPM burst #{calls['n']}")

    monkeypatch.setattr(llm, "_create", fake_create)
    with llm.collect_provenance() as records:
        with pytest.raises(RuntimeError, match="TPM burst #4"):
            llm._call_cerebras_strict("p", 0.0, system_prompt="s", max_tokens=None)
    assert calls["n"] == 4  # 1 + 3 retries
    assert records[0].rate_limited is True


def test_strict_path_never_routes_to_groq_or_gemini(llm, monkeypatch):
    """If the Cerebras path is in use, neither Groq route nor Gemini is invoked."""
    monkeypatch.setenv("LLM_STRICT_PRIMARY", "cerebras")
    monkeypatch.setattr(llm, "_create", lambda *a, **k: "primary-only-output")

    # Booby-trap the fallback paths: calling either is a test failure.
    def _trap_groq(*a, **k):
        raise AssertionError("Groq route must not be called when strict primary is on")

    def _trap_gemini(*a, **k):
        raise AssertionError("Gemini must not be called when strict primary is on")

    monkeypatch.setattr(llm, "_call_groq_route", _trap_groq)
    monkeypatch.setattr(llm, "_create_gemini", _trap_gemini)

    with llm.collect_provenance() as records:
        out = llm.call_llm("prompt", temperature=0.0)
    assert out == "primary-only-output"
    assert len(records) == 1
    assert records[0].is_fallback is False
