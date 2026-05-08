"""LLM call layer with circuit-breaker fallback and per-call provenance.

Design
------
Resilient production order (keys permitting):

1. **Groq primary** (``groq_model``, default ``openai/gpt-oss-120b``) — TPM jitter
   retry + ``PrimaryCircuit`` on this tier only.

2. **Groq fallback** (``groq_fallback_model``, default Llama 3.3 70B) — when the
   primary is rate-limited (incl. circuit-open short-circuit to this model) or
   after TPM retry exhaustion.

3. **Gemini** (``gemini_model``) — last resort when both Groq tiers fail with
   saturation-class errors and ``GEMINI_API_KEY`` is set.

Evaluation: ``EVAL_GEMINI_ONLY=1`` with a Gemini key pins **Gemini only**.
Otherwise ``GROQ_STRICT_PRIMARY=1`` forces **Groq primary only** (no 70b
substitution) for the Groq path; production-style Groq→fallback→Gemini still
applies when strict is off.

Optional ``GROQ_DISABLE_GEMINI_FALLBACK=1`` skips Gemini after Groq failure.

Per-call provenance is exposed through :func:`collect_provenance`.
"""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

from groq import Groq

from app.config import get_settings
from app.services.observability import record_llm_call

logger = logging.getLogger(__name__)

settings = get_settings()
_client = Groq(api_key=settings.groq_api_key, max_retries=0)


def _gemini_fallback_allowed() -> bool:
    """When false (``GROQ_DISABLE_GEMINI_FALLBACK``), Groq failure does not route to Gemini."""
    return (os.getenv("GROQ_DISABLE_GEMINI_FALLBACK") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class CallRecord:
    """Immutable record of a single LLM round-trip.

    ``rate_limited`` is true when the primary model returned 429 at least once
    during this logical call, even if a retry eventually succeeded. Eval
    callers use this to decide whether the measurement is trustworthy.
    """

    model: str
    is_fallback: bool
    rate_limited: bool
    error: str | None = None


_provenance_scope: ContextVar[list[CallRecord] | None] = ContextVar(
    "llm_provenance_scope",
    default=None,
)
_call_context: ContextVar[dict | None] = ContextVar("llm_call_context", default=None)

_fallback_count = 0

_gemini_lock = threading.Lock()
_gemini_client: Any | None = None
_gemini_client_sig: tuple[Any, ...] | None = None


def _strict_primary() -> bool:
    return (os.getenv("GROQ_STRICT_PRIMARY") or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_rate_limit(exc: BaseException) -> bool:
    msg = str(exc)
    return "429" in msg or "rate_limit" in msg


def _classify_rate_limit(exc_str: str) -> str | None:
    """Return ``"tpm"``, ``"tpd"``, ``"rpm"``, ``"rpd"`` or ``None``.

    Groq's 429 messages name the exhausted bucket explicitly (e.g. ``"on tokens
    per day (TPD)"``). Differentiating matters: TPM/RPM resets within a minute
    so retrying makes sense, while TPD/RPD only resets at the next UTC day so
    in-process retry is a guaranteed waste. Sweep logs from 2026-04-18 showed
    five ``try again in 845s`` retries per sample after a TPD trip — minutes of
    pipeline time burned on a window that won't reset until midnight.
    """

    text = exc_str.lower()
    if "tokens per day" in text or "(tpd)" in text:
        return "tpd"
    if "tokens per minute" in text or "(tpm)" in text:
        return "tpm"
    if "requests per day" in text or "(rpd)" in text:
        return "rpd"
    if "requests per minute" in text or "(rpm)" in text:
        return "rpm"
    return None


def _is_daily_quota(exc_str: str) -> bool:
    kind = _classify_rate_limit(exc_str)
    return kind in {"tpd", "rpd"}


def _wait_from_error(exc_str: str) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", exc_str)
    if m:
        return float(m.group(1)) + 1
    m = re.search(r"try again in (\d+)m", exc_str)
    if m:
        return float(m.group(1)) * 60 + 5
    return 15



class PrimaryCircuit:
    """Circuit breaker for the primary model.

    States:
    - ``closed``: primary is healthy; ``should_call_primary`` returns True.
    - ``open``: primary recently rate-limited; stays open until ``open_until``.
    - ``half_open``: cooldown elapsed; *one* probe call is allowed. Success
      closes the circuit; another failure re-opens it with exponential
      back-off (capped).

    We intentionally do **not** use a long wall-clock window of "prefer
    fallback": that pattern, used in the previous implementation, turned a
    single 429 into a ≤5 minute period during which every call was routed
    to the weaker fallback model even if the primary had recovered. A probe
    semantics is the textbook fix (Fowler, CircuitBreaker).
    """

    _MIN_COOLDOWN = 10.0
    _MAX_COOLDOWN = 180.0

    def __init__(self) -> None:
        self._open_until: float = 0.0
        self._last_wait_hint: float = 0.0
        self._half_open_pending: bool = False
        self._consecutive_failures: int = 0

    def state(self) -> str:
        now = time.monotonic()
        if now < self._open_until:
            return "open"
        if self._half_open_pending or self._consecutive_failures > 0:
            return "half_open"
        return "closed"

    def should_call_primary(self) -> bool:
        """True when the primary should be attempted (closed or half-open)."""
        now = time.monotonic()
        if now >= self._open_until:
            self._half_open_pending = True
            return True
        return False

    def record_success(self) -> None:
        self._open_until = 0.0
        self._last_wait_hint = 0.0
        self._half_open_pending = False
        self._consecutive_failures = 0

    def record_rate_limit(self, wait_hint: float) -> None:
        self._consecutive_failures += 1
        cool = max(self._MIN_COOLDOWN, min(wait_hint, self._MAX_COOLDOWN))
        cool *= min(self._consecutive_failures, 3)
        self._open_until = time.monotonic() + min(cool, self._MAX_COOLDOWN)
        self._last_wait_hint = wait_hint
        self._half_open_pending = False


_circuit = PrimaryCircuit()


def _record_provenance(record: CallRecord) -> None:
    records = _provenance_scope.get()
    if records is not None:
        records.append(record)


@contextmanager
def collect_provenance() -> Iterator[list[CallRecord]]:
    """Collect per-call provenance inside this ``with`` block.

    The eval pipeline runner wraps a single sample's ``pipeline.invoke`` with
    this and then summarises the records (e.g. how many calls used the
    fallback). Nested scopes are supported via ``ContextVar.reset``; records
    are not shared across unrelated callers.
    """
    records: list[CallRecord] = []
    token = _provenance_scope.set(records)
    try:
        yield records
    finally:
        _provenance_scope.reset(token)


@contextmanager
def llm_call_context(**metadata: object) -> Iterator[None]:
    """Attach node/purpose metadata to all LLM calls in this scope."""
    parent = _call_context.get() or {}
    merged = {**parent, **{k: v for k, v in metadata.items() if v is not None}}
    token = _call_context.set(merged)
    try:
        yield
    finally:
        _call_context.reset(token)


def _gemini_configured() -> bool:
    key = settings.gemini_api_key
    return bool(key and str(key).strip())


def _gemini_error_allows_groq_fallback(exc: BaseException) -> bool:
    """True when Gemini failed for saturation/quota so Groq may complete the call."""
    msg = str(exc).lower()
    if "timeout" in msg:
        return True
    if "timed out" in msg:
        return True
    if "429" in msg:
        return True
    if "resource exhausted" in msg:
        return True
    if "resourceexhausted" in msg.replace(" ", ""):
        return True
    if "too many requests" in msg:
        return True
    if "quota" in msg and ("exceed" in msg or "exhaust" in msg):
        return True
    if "rate limit" in msg:
        return True
    if "503" in msg:
        return True
    if "unavailable" in msg:
        return True
    return False


def _groq_failure_allows_gemini_fallback(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if _is_rate_limit(exc):
        return True
    if "timeout" in msg or "timed out" in msg:
        return True
    if "503" in msg or "502" in msg or "500" in msg:
        return True
    if "connection" in msg:
        return True
    return False


def _gemini_debug_enabled() -> bool:
    return (os.getenv("GEMINI_DEBUG") or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_gemini_client() -> Any:
    """Reuse one ``genai.Client`` per process so HTTP keep-alive applies across calls.

    Creating a new client per request was observed to force a ~300s first-byte
    delay on each call (free-tier queue on cold connect); the same client’s
    second request returned in ~1s in ``scripts/gemini_one_shot_latency.py``.
    """
    from google import genai
    from google.genai import types

    global _gemini_client, _gemini_client_sig
    timeout_ms = max(1, int(float(settings.gemini_http_timeout_seconds) * 1000))
    retry_attempts = settings.gemini_http_retry_attempts
    retry_opts = (
        types.HttpRetryOptions(attempts=max(1, int(retry_attempts)))
        if retry_attempts is not None
        else None
    )
    http_kw: dict[str, object] = {"timeout": timeout_ms}
    if retry_opts is not None:
        http_kw["retry_options"] = retry_opts
    sig = (
        str(settings.gemini_api_key or ""),
        timeout_ms,
        retry_attempts,
    )
    with _gemini_lock:
        if _gemini_client is not None and _gemini_client_sig == sig:
            return _gemini_client
        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(**http_kw),
        )
        _gemini_client_sig = sig
        return _gemini_client


def reset_gemini_client_for_tests() -> None:
    """Test hook: drop cached Gemini client (e.g. after monkeypatching HTTP settings)."""
    global _gemini_client, _gemini_client_sig
    with _gemini_lock:
        _gemini_client = None
        _gemini_client_sig = None


def warmup_gemini_connection() -> None:
    """Best-effort minimal request so the shared client opens TLS + HTTP before real work.

    Does nothing when Gemini is not configured. Logs duration on success; logs a warning on
    failure without raising (worker startup and keepalive must not crash the process).
    """
    if not _gemini_configured():
        return
    from google.genai import types

    tb = int(settings.gemini_thinking_budget)
    model_name = settings.gemini_model
    started = time.perf_counter()
    try:
        client = _get_gemini_client()
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=16,
            system_instruction="Reply with exactly the word ok.",
            thinking_config=types.ThinkingConfig(thinking_budget=tb),
        )
        client.models.generate_content(model=model_name, contents="ping", config=config)
        logger.info(
            "gemini warmup ok model=%s thinking_budget=%s elapsed_s=%.2f",
            model_name,
            tb,
            time.perf_counter() - started,
        )
    except Exception:
        logger.warning("gemini warmup failed", exc_info=True)


def _create_gemini(
    prompt: str,
    temperature: float,
    *,
    system_prompt: str = "Return JSON only.",
    max_tokens: int | None = None,
) -> str:
    from google.genai import types

    started = time.perf_counter()
    timeout_ms = max(1, int(float(settings.gemini_http_timeout_seconds) * 1000))
    retry_attempts = settings.gemini_http_retry_attempts
    client = _get_gemini_client()
    out_cap = int(max_tokens) if isinstance(max_tokens, int) and max_tokens > 0 else 1024
    tb = int(settings.gemini_thinking_budget)
    model_name = settings.gemini_model
    if _gemini_debug_enabled():
        logger.info(
            "Gemini request: model=%s thinking_budget=%s timeout_ms=%s http_retry_attempts=%s",
            model_name,
            tb,
            timeout_ms,
            retry_attempts if retry_attempts is not None else "sdk_default",
        )
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=out_cap,
        system_instruction=system_prompt,
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=tb),
    )
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    usage = getattr(response, "usage_metadata", None)
    pt = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
    ct = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
    tt = int(getattr(usage, "total_token_count", 0) or 0) if usage else 0
    if not tt:
        tt = pt + ct
    record_llm_call(
        model=model_name,
        model_tier="gemini",
        latency_ms=latency_ms,
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=tt,
        call_context=_call_context.get(),
    )
    try:
        content = response.text
    except Exception:
        content = None
    return content or "[]"


def _create(
    model: str,
    prompt: str,
    temperature: float,
    *,
    tier: str,
    system_prompt: str = "Return JSON only.",
    max_tokens: int | None = None,
) -> str:
    started = time.perf_counter()
    kwargs: dict[str, object] = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    if isinstance(max_tokens, int) and max_tokens > 0:
        kwargs["max_tokens"] = max_tokens
    response = _client.chat.completions.create(
        **kwargs,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    record_llm_call(
        model=model,
        model_tier=tier,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        call_context=_call_context.get(),
    )
    content = response.choices[0].message.content if response.choices else None
    return content or "[]"


def _call_groq_route(
    prompt: str,
    temperature: float,
    *,
    system_prompt: str,
    max_tokens: int | None,
    strict: bool,
) -> str:
    """Groq ``groq_model`` with circuit breaker, TPM retry, then ``groq_fallback_model``."""
    global _fallback_count
    primary = settings.groq_model
    fallback = (settings.groq_fallback_model or "").strip()

    if strict:
        try:
            out = _create(
                primary,
                prompt,
                temperature,
                tier="primary",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            if _is_rate_limit(exc):
                kind = _classify_rate_limit(str(exc))
                record_llm_call(
                    model=primary,
                    model_tier="primary",
                    latency_ms=0,
                    error=str(exc)[:300],
                    rate_limit_kind=kind,
                    call_context=_call_context.get(),
                )
                _record_provenance(
                    CallRecord(model=primary, is_fallback=False, rate_limited=True, error=str(exc)[:200])
                )
            raise
        _record_provenance(CallRecord(model=primary, is_fallback=False, rate_limited=False))
        return out

    use_primary = _circuit.should_call_primary()
    if not use_primary:
        if not fallback:
            raise RuntimeError("primary circuit open and groq_fallback_model is not configured")
        _fallback_count += 1
        out = _create(
            fallback,
            prompt,
            temperature,
            tier="fallback",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        _record_provenance(CallRecord(model=fallback, is_fallback=True, rate_limited=False))
        return out

    first_exc_str: str
    try:
        out = _create(
            primary,
            prompt,
            temperature,
            tier="primary",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        _circuit.record_success()
        _record_provenance(CallRecord(model=primary, is_fallback=False, rate_limited=False))
        return out
    except Exception as exc:
        if not _is_rate_limit(exc):
            raise
        first_exc_str = str(exc)
        wait_hint = _wait_from_error(first_exc_str)
        rl_kind = _classify_rate_limit(first_exc_str)
        daily = rl_kind in {"tpd", "rpd"}
        if daily:
            _circuit.record_rate_limit(wait_hint)
        else:
            _circuit.record_rate_limit(wait_hint)
        record_llm_call(
            model=primary,
            model_tier="primary",
            latency_ms=0,
            error=first_exc_str[:300],
            rate_limit_kind=rl_kind,
            call_context=_call_context.get(),
        )
        if not fallback:
            raise
        if daily:
            _fallback_count += 1
            out = _create(
                fallback,
                prompt,
                temperature,
                tier="fallback",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
            _record_provenance(CallRecord(model=fallback, is_fallback=True, rate_limited=True))
            return out

    delay = min(_wait_from_error(first_exc_str), 20) * (0.85 + random.random() * 0.3)
    time.sleep(delay)
    try:
        out = _create(
            primary,
            prompt,
            temperature,
            tier="primary",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        _circuit.record_success()
        _record_provenance(CallRecord(model=primary, is_fallback=False, rate_limited=True))
        return out
    except Exception as exc2:
        if not _is_rate_limit(exc2):
            raise
        rl2 = _classify_rate_limit(str(exc2))
        record_llm_call(
            model=primary,
            model_tier="primary",
            latency_ms=0,
            error=str(exc2)[:300],
            rate_limit_kind=rl2,
            call_context=_call_context.get(),
        )
        _circuit.record_rate_limit(_wait_from_error(str(exc2)))
        if not fallback:
            raise
        _fallback_count += 1
        out = _create(
            fallback,
            prompt,
            temperature,
            tier="fallback",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        _record_provenance(CallRecord(model=fallback, is_fallback=True, rate_limited=True))
        return out


def call_llm(
    prompt: str,
    temperature: float = 0.0,
    *,
    system_prompt: str = "Return JSON only.",
    max_tokens: int | None = None,
) -> str:
    """Groq primary → Groq fallback → Gemini (see module docstring)."""
    global _fallback_count
    strict = _strict_primary()
    gem = _gemini_configured()
    mid = settings.gemini_model
    gemini_only = (os.getenv("EVAL_GEMINI_ONLY") or "").strip().lower() in {"1", "true", "yes", "on"}

    if gem and strict and gemini_only:
        try:
            out = _create_gemini(
                prompt,
                temperature,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            saturated = _gemini_error_allows_groq_fallback(exc)
            record_llm_call(
                model=mid,
                model_tier="gemini",
                latency_ms=0,
                error=str(exc)[:300],
                rate_limit_kind="rpd" if "per day" in str(exc).lower() else ("rpm" if saturated else None),
                call_context=_call_context.get(),
            )
            _record_provenance(
                CallRecord(
                    model=mid,
                    is_fallback=False,
                    rate_limited=saturated,
                    error=str(exc)[:200],
                )
            )
            raise
        _record_provenance(CallRecord(model=mid, is_fallback=False, rate_limited=False))
        return out

    try:
        return _call_groq_route(
            prompt,
            temperature,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            strict=strict,
        )
    except Exception as groq_exc:
        if not gem:
            raise
        if not _gemini_fallback_allowed():
            raise
        if not _groq_failure_allows_gemini_fallback(groq_exc):
            raise

    _fallback_count += 1
    out = _create_gemini(
        prompt,
        temperature,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )
    _record_provenance(CallRecord(model=mid, is_fallback=True, rate_limited=False))
    return out


def get_fallback_count() -> int:
    """Process-wide count of fallback-model calls (unchanged API for back-compat)."""
    return _fallback_count


def get_current_provenance() -> list[CallRecord]:
    """Return a snapshot of the provenance records active in this scope.

    Returns an empty list when called outside :func:`collect_provenance`. The
    copy makes callers immune to subsequent mutations if the pipeline keeps
    making LLM calls after the snapshot.
    """
    records = _provenance_scope.get()
    return list(records) if records is not None else []


def summarize_provenance(records: list[CallRecord] | None = None) -> dict:
    """Aggregate provenance records into a small JSON-serialisable dict.

    This is the ground truth for "did this pipeline run use the fallback
    model?" — a question the old ``fallback_used`` flag on
    ``obs:pipeline:runs`` could not answer (it only checked for a specific
    error string in the normalize node, not actual LLM routing). Keys:

    - ``llm_calls_total`` – total LLM round-trips in scope
    - ``llm_fallback_calls`` – round-trips marked ``is_fallback`` (Groq 70b or Gemini last resort)
    - ``llm_fallback_used`` – True iff at least one such call
    - ``llm_rate_limited_calls`` – round-trips that saw a 429 (even if retried)
    - ``llm_models`` – ordered list of models used
    """
    data = get_current_provenance() if records is None else list(records)
    models: list[str] = []
    fallback_calls = 0
    rl_calls = 0
    for rec in data:
        if not isinstance(rec, CallRecord):
            continue
        models.append(rec.model)
        if rec.is_fallback:
            fallback_calls += 1
        if rec.rate_limited:
            rl_calls += 1
    return {
        "llm_calls_total": len(models),
        "llm_fallback_calls": fallback_calls,
        "llm_fallback_used": fallback_calls > 0,
        "llm_rate_limited_calls": rl_calls,
        "llm_models": models,
    }


def reset_circuit_for_tests() -> None:
    """Test hook: force the circuit back to a clean state."""
    global _circuit, _fallback_count
    _circuit = PrimaryCircuit()
    _fallback_count = 0
    reset_gemini_client_for_tests()
