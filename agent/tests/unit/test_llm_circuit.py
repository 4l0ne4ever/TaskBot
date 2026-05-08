"""Unit tests for the LLM call layer's fallback and provenance semantics."""

from __future__ import annotations

import pytest

from app.pipeline import llm as llm_module


class _RateLimitError(RuntimeError):
    pass


def _make_rate_limit_exc(wait: str = "2s") -> _RateLimitError:
    return _RateLimitError(f"Error code: 429, message: try again in {wait}")


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    llm_module.reset_circuit_for_tests()
    monkeypatch.setattr(llm_module.settings, "groq_model", "primary-model")
    monkeypatch.setattr(llm_module.settings, "groq_fallback_model", "fallback-model")
    yield
    llm_module.reset_circuit_for_tests()


def test_strict_mode_propagates_rate_limit(monkeypatch):
    monkeypatch.setenv("GROQ_STRICT_PRIMARY", "1")

    def _boom(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        raise _make_rate_limit_exc("3s")

    monkeypatch.setattr(llm_module, "_create", _boom)

    with llm_module.collect_provenance() as records:
        with pytest.raises(_RateLimitError):
            llm_module.call_llm("hi")

    assert len(records) == 1
    assert records[0].model == "primary-model"
    assert records[0].is_fallback is False
    assert records[0].rate_limited is True


def test_resilient_uses_groq_before_gemini_when_both_configured(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(llm_module.settings, "gemini_model", "gemini-test")

    gemini_calls = 0

    def _no_gemini(*_a, **_k):
        nonlocal gemini_calls
        gemini_calls += 1
        raise AssertionError("Gemini must not run when Groq primary succeeds")

    monkeypatch.setattr(llm_module, "_create_gemini", _no_gemini)

    def _groq(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (prompt, temperature, system_prompt, max_tokens)
        assert model == "primary-model"
        return '{"ok": true}'

    monkeypatch.setattr(llm_module, "_create", _groq)

    with llm_module.collect_provenance() as records:
        out = llm_module.call_llm("hi")

    assert out == '{"ok": true}'
    assert gemini_calls == 0
    assert records[0].model == "primary-model"


def test_strict_mode_does_not_fallback_even_if_configured(monkeypatch):
    monkeypatch.setenv("GROQ_STRICT_PRIMARY", "1")
    calls: list[str] = []

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        calls.append(model)
        raise _make_rate_limit_exc("2s")

    monkeypatch.setattr(llm_module, "_create", _fake)

    with pytest.raises(_RateLimitError):
        llm_module.call_llm("hi")

    assert calls == ["primary-model"], "strict mode must not invoke fallback"


def test_nonstrict_falls_back_after_primary_keeps_failing(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.time, "sleep", lambda _s: None)
    calls: list[str] = []

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        calls.append(model)
        if model == "primary-model":
            raise _make_rate_limit_exc("1s")
        return '{"tasks": []}'

    monkeypatch.setattr(llm_module, "_create", _fake)

    with llm_module.collect_provenance() as records:
        out = llm_module.call_llm("hi")

    assert out == '{"tasks": []}'
    assert calls == ["primary-model", "primary-model", "fallback-model"]
    assert records[-1].model == "fallback-model"
    assert records[-1].is_fallback is True
    assert records[-1].rate_limited is True


def test_circuit_probes_primary_after_cooldown(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.time, "sleep", lambda _s: None)

    mono = {"t": 1_000.0}
    monkeypatch.setattr(llm_module.time, "monotonic", lambda: mono["t"])

    attempt = {"n": 0}

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        attempt["n"] += 1
        if model == "primary-model" and attempt["n"] <= 2:
            raise _make_rate_limit_exc("1s")
        return '{"tasks": []}'

    monkeypatch.setattr(llm_module, "_create", _fake)

    llm_module.call_llm("first")
    assert llm_module._circuit.state() in {"open", "half_open"}

    mono["t"] += 10_000.0

    with llm_module.collect_provenance() as records:
        out = llm_module.call_llm("second")

    assert out == '{"tasks": []}'
    assert records[0].model == "primary-model"
    assert records[0].is_fallback is False
    assert llm_module._circuit.state() == "closed"


def test_provenance_scope_is_isolated(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(
        llm_module,
        "_create",
        lambda m, p, t, *, tier, system_prompt="Return JSON only.", max_tokens=None: '{"tasks": []}',
    )

    with llm_module.collect_provenance() as outer:
        llm_module.call_llm("a")
        with llm_module.collect_provenance() as inner:
            llm_module.call_llm("b")
        llm_module.call_llm("c")

    assert len(inner) == 1
    assert len(outer) == 2
    assert all(r.model == "primary-model" for r in outer + inner)


def test_fallback_counter_reflects_fallback_calls(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.time, "sleep", lambda _s: None)

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        if model == "primary-model":
            raise _make_rate_limit_exc("1s")
        return "{}"

    monkeypatch.setattr(llm_module, "_create", _fake)
    before = llm_module.get_fallback_count()
    llm_module.call_llm("x")
    assert llm_module.get_fallback_count() == before + 1


def test_summarize_provenance_reports_fallback_routing(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.time, "sleep", lambda _s: None)

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        if model == "primary-model":
            raise _make_rate_limit_exc("1s")
        return "{}"

    monkeypatch.setattr(llm_module, "_create", _fake)

    with llm_module.collect_provenance():
        llm_module.call_llm("a")
        summary = llm_module.summarize_provenance()

    assert summary["llm_calls_total"] >= 1
    assert summary["llm_fallback_used"] is True
    assert summary["llm_fallback_calls"] >= 1
    assert summary["llm_rate_limited_calls"] >= 1
    assert "fallback-model" in summary["llm_models"]


def test_summarize_provenance_empty_outside_scope(monkeypatch):
    summary = llm_module.summarize_provenance()
    assert summary == {
        "llm_calls_total": 0,
        "llm_fallback_calls": 0,
        "llm_fallback_used": False,
        "llm_rate_limited_calls": 0,
        "llm_models": [],
    }


def test_daily_quota_skips_in_process_retry_and_falls_back(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    sleeps: list[float] = []
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: sleeps.append(s))
    calls: list[str] = []

    def _fake(model, prompt, temperature, *, tier, system_prompt="Return JSON only.", max_tokens=None):
        _ = (tier, system_prompt, max_tokens)
        calls.append(model)
        if model == "primary-model":
            raise _RateLimitError(
                "Error code: 429 - Rate limit reached for model `primary-model` "
                "service tier `on_demand` on tokens per day (TPD): Limit 100000, "
                "Used 100000, Requested 1024. Please try again in 845s."
            )
        return "{}"

    monkeypatch.setattr(llm_module, "_create", _fake)

    out = llm_module.call_llm("daily-quota-trip")

    assert out == "{}"
    assert calls == ["primary-model", "fallback-model"], (
        "TPD must short-circuit straight to fallback (no in-process probe retry)"
    )
    assert sleeps == [], "must not sleep on a daily-window backoff"


def test_classify_rate_limit_recognizes_tpd_and_tpm():
    assert llm_module._classify_rate_limit("on tokens per day (TPD): Limit") == "tpd"
    assert llm_module._classify_rate_limit("on tokens per minute (TPM): Limit") == "tpm"
    assert llm_module._classify_rate_limit("requests per day (RPD)") == "rpd"
    assert llm_module._classify_rate_limit("requests per minute (RPM)") == "rpm"
    assert llm_module._classify_rate_limit("plain 429 with no marker") is None


def test_summarize_provenance_primary_only_run(monkeypatch):
    monkeypatch.setenv("GROQ_STRICT_PRIMARY", "1")
    monkeypatch.setattr(
        llm_module,
        "_create",
        lambda m, p, t, *, tier, system_prompt="Return JSON only.", max_tokens=None: "{}",
    )

    with llm_module.collect_provenance():
        llm_module.call_llm("x")
        llm_module.call_llm("y")
        summary = llm_module.summarize_provenance()

    assert summary["llm_fallback_used"] is False
    assert summary["llm_fallback_calls"] == 0
    assert summary["llm_calls_total"] == 2
    assert summary["llm_models"] == ["primary-model", "primary-model"]


def test_groq_stack_exhausted_then_gemini(monkeypatch):
    monkeypatch.delenv("GROQ_STRICT_PRIMARY", raising=False)
    monkeypatch.setattr(llm_module.settings, "gemini_api_key", "gk")
    monkeypatch.setattr(llm_module.settings, "gemini_model", "gemini-test")

    def _boom(*_a, **_k):
        raise _make_rate_limit_exc("1s")

    monkeypatch.setattr(llm_module, "_call_groq_route", _boom)
    monkeypatch.setattr(llm_module, "_create_gemini", lambda *a, **k: '{"g":1}')

    with llm_module.collect_provenance() as records:
        out = llm_module.call_llm("z")

    assert out.strip() == '{"g":1}'
    assert records[-1].model == "gemini-test"
    assert records[-1].is_fallback is True
