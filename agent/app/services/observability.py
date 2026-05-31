from __future__ import annotations

import json
import os
import random
import time
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
_warned_once: set[str] = set()
_redis_unavailable: bool = False


class _SettingsProxy:
    """Delegates to :func:`get_settings` so env reloads apply; tests may override attrs."""

    __slots__ = ("_overrides",)

    def __init__(self) -> None:
        object.__setattr__(self, "_overrides", {})

    def __getattr__(self, name: str) -> Any:
        o: dict[str, Any] = object.__getattribute__(self, "_overrides")
        if name in o:
            return o[name]
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_overrides":
            object.__setattr__(self, name, value)
        else:
            object.__getattribute__(self, "_overrides")[name] = value


settings = _SettingsProxy()


def _warn_observability_once(key: str, message: str, *args: object) -> None:
    if key in _warned_once:
        return
    _warned_once.add(key)
    logger.warning(message, *args)


def _mark_redis_unavailable(exc: BaseException) -> None:
    global _redis_unavailable
    _redis_unavailable = True
    url = settings.redis_url
    _warn_observability_once(
        "redis_unavailable",
        "observability: Redis at %s unreachable (%s). "
        "Host-side tools must use the published host port: set REDIS_PUBLISH_PORT (or REDIS_URL) "
        "to match Docker/OrbStack left-hand port (e.g. 56379:6379 → 56379). Telemetry retries skipped until restart.",
        url,
        type(exc).__name__,
    )


def probe_redis_health() -> bool:
    """Test the observability Redis connection eagerly at startup.

    Call once when the pipeline or worker initialises so a misconfigured
    REDIS_URL (wrong host port, Docker/OrbStack publish port mismatch) is
    flagged immediately with an actionable log message rather than silently
    dropping every telemetry write until the first one fails.

    Sets the module-level ``_redis_unavailable`` flag and returns
    ``False`` when unreachable; returns ``True`` if Redis responded or if
    observability is disabled (disabled ≠ broken).
    """
    # _redis_unavailable is mutated by _mark_redis_unavailable, not here,
    # so no `global` declaration is needed.
    if not settings.redis_observability_enabled:
        return True
    if _redis_unavailable:
        return False
    try:
        client = _redis_client()
        client.ping()
        logger.info("observability: Redis health probe OK (%s)", settings.redis_url)
        return True
    except (redis.ConnectionError, redis.TimeoutError, OSError) as exc:
        _mark_redis_unavailable(exc)
        return False


def _langsmith_session_name() -> str:
    """Eval can set LANGSMITH_SESSION_NAME so runs group in LangSmith apart from production."""
    return (os.getenv("LANGSMITH_SESSION_NAME") or "").strip() or settings.langsmith_project


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=float(settings.redis_socket_connect_timeout_seconds),
    )


def _redis_store(fn) -> None:
    """Run ``fn(redis_client)`` unless Redis is disabled or already marked unavailable.

    Catches all exceptions so observability never crashes the pipeline — any
    failure from the Redis client or the callback is treated as unavailability.
    """
    if _redis_unavailable:
        return
    if not settings.redis_observability_enabled:
        return
    try:
        fn(_redis_client())
    except (redis.ConnectionError, redis.TimeoutError, OSError) as exc:
        _mark_redis_unavailable(exc)
    except Exception as exc:
        _mark_redis_unavailable(exc)


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    in_cost = (prompt_tokens / 1_000_000) * float(settings.groq_input_cost_per_million_tokens)
    out_cost = (completion_tokens / 1_000_000) * float(settings.groq_output_cost_per_million_tokens)
    return round(in_cost + out_cost, 8)


def _record_langsmith_ingest_event(
    *,
    outcome: str,
    run_name: str,
    status_code: int | None = None,
    detail: str | None = None,
) -> None:
    """Count LangSmith /runs POST outcomes in Redis so 429s and transport
    failures are visible even though the pipeline must never depend on ingest.
    Keys: ``obs:langsmith:ingest:counts`` (hash), ``obs:langsmith:ingest:events`` (list).
    """
    ts = datetime.now(UTC).isoformat()

    def _persist(r: redis.Redis) -> None:
        hkey = "obs:langsmith:ingest:counts"
        pipe = r.pipeline()
        pipe.hincrby(hkey, "attempts", 1)
        if outcome == "success":
            pipe.hincrby(hkey, "success", 1)
        elif outcome == "http_error":
            pipe.hincrby(hkey, "http_error", 1)
            if status_code == 429:
                pipe.hincrby(hkey, "http_429", 1)
            elif status_code is not None and 400 <= status_code < 500:
                pipe.hincrby(hkey, "http_4xx_other", 1)
            elif status_code is not None and status_code >= 500:
                pipe.hincrby(hkey, "http_5xx", 1)
        elif outcome == "transport_error":
            pipe.hincrby(hkey, "transport_error", 1)
        pipe.execute()

        ev = {
            "ts": ts,
            "outcome": outcome,
            "status_code": status_code,
            "run_name": run_name,
            "detail": (detail or "")[:200],
        }
        ek = "obs:langsmith:ingest:events"
        r.lpush(ek, json.dumps(ev))
        r.ltrim(ek, 0, 499)

    _redis_store(_persist)


def _post_langsmith_run(payload: dict[str, Any]) -> None:
    """POST one run record to LangSmith with bounded exponential-backoff retry.

    Retry policy (configurable via Settings):
    - ``langsmith_ingest_max_retries`` attempts total (default 3).
    - Exponential backoff with full jitter between retries so concurrent
      pipeline runs don't all fire at the same time after a 429 burst:
      ``delay = base * 2^(attempt-1) + uniform(0, base)``.
    - Retry on 5xx and 429 (transient server-side errors).
    - No retry on other 4xx (permanent client errors — retrying is useless).
    - On retry exhaustion a ``retry_exhausted`` counter is incremented in
      ``obs:langsmith:ingest:counts`` so the SLO snapshot surfaces it.
    - Pipeline never blocks on LangSmith: the method returns normally
      regardless of outcome — tracing is a side channel.
    """
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return
    run_name = str(payload.get("name") or "unknown")
    headers = {
        "x-api-key": settings.langsmith_api_key,
        "content-type": "application/json",
    }
    url = f"{settings.langsmith_api_url.rstrip('/')}/runs"
    timeout = float(settings.langsmith_ingest_timeout_seconds)
    max_retries = max(1, int(settings.langsmith_ingest_max_retries))
    backoff_base = max(0.1, float(settings.langsmith_ingest_retry_backoff_base_seconds))

    last_outcome = "transport_error"
    last_status_code: int | None = None
    last_detail: str | None = None
    succeeded = False

    for attempt in range(max_retries):
        if attempt > 0:
            delay = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, backoff_base)
            time.sleep(delay)
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
            if 200 <= resp.status_code < 300:
                _record_langsmith_ingest_event(outcome="success", run_name=run_name)
                succeeded = True
                break
            last_status_code = resp.status_code
            last_detail = (resp.text or "")[:200] or None
            last_outcome = "http_error"
            # Permanent client errors — no point retrying
            if resp.status_code != 429 and 400 <= resp.status_code < 500:
                break
        except httpx.TimeoutException:
            last_outcome = "transport_error"
            last_detail = "timeout"
        except httpx.RequestError as exc:
            last_outcome = "transport_error"
            last_detail = type(exc).__name__
        except Exception as exc:
            last_outcome = "transport_error"
            last_detail = type(exc).__name__

    if not succeeded:
        _record_langsmith_ingest_event(
            outcome=last_outcome,
            run_name=run_name,
            status_code=last_status_code,
            detail=last_detail,
        )
        if max_retries > 1:
            def _inc_exhausted(r: redis.Redis) -> None:
                pipe = r.pipeline()
                pipe.hincrby("obs:langsmith:ingest:counts", "retry_exhausted", 1)
                pipe.execute()
            _redis_store(_inc_exhausted)


def record_llm_call(
    *,
    model: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    error: str | None = None,
    model_tier: str | None = None,
    rate_limit_kind: str | None = None,
    call_context: dict[str, Any] | None = None,
) -> None:
    """Persist one LLM round-trip to Redis + LangSmith.

    ``model_tier`` is ``"primary"`` / ``"fallback"`` and is the ground truth
    for "which routing tier produced this call?". Prior to this, tier had to
    be inferred from the model name, which collapses as soon as the configured
    fallback changes or two pipelines share a process with different configs.

    ``rate_limit_kind`` tags 429s as ``"tpm"`` (tokens-per-minute — retrying is
    worth it) or ``"tpd"`` (tokens-per-day — retrying in-process is pointless).
    This unlocks per-window quota dashboards without grepping error strings.
    """

    ts = datetime.now(UTC).isoformat()
    cost = _estimate_cost(prompt_tokens, completion_tokens)
    ctx = call_context if isinstance(call_context, dict) else {}
    sid = (os.getenv("EVAL_TRACE_SAMPLE_ID") or "").strip()
    rid = (os.getenv("EVAL_RUN_ID") or "").strip()
    row = {
        "ts": ts,
        "model": model,
        "model_tier": model_tier,
        "eval_run_id": rid or None,
        "sample_id": sid or None,
        "node_name": ctx.get("node_name"),
        "call_purpose": ctx.get("call_purpose"),
        "retry_attempt": ctx.get("retry_attempt"),
        "chunk_index": ctx.get("chunk_index"),
        "chunk_count": ctx.get("chunk_count"),
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_estimate": cost,
        "error": error,
        "rate_limit_kind": rate_limit_kind,
    }
    def _persist_llm(r: redis.Redis) -> None:
        key = "obs:llm:calls"
        r.lpush(key, json.dumps(row))
        r.ltrim(key, 0, 2999)

    _redis_store(_persist_llm)

    inputs: dict[str, Any] = {"model": model, "model_tier": model_tier}
    if sid:
        inputs["sample_id"] = sid
    if rid:
        inputs["eval_run_id"] = rid
    for key in ("node_name", "call_purpose", "retry_attempt", "chunk_index", "chunk_count"):
        val = ctx.get(key)
        if val is not None:
            inputs[key] = val
    _post_langsmith_run(
        {
            "id": str(uuid4()),
            "name": "groq_chat_completion",
            "run_type": "llm",
            "session_name": _langsmith_session_name(),
            "inputs": inputs,
            "outputs": {"error": error, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            "start_time": ts,
            "end_time": datetime.now(UTC).isoformat(),
            "error": error,
            "extra": {
                "latency_ms": round(latency_ms, 2),
                "total_tokens": total_tokens,
                "cost_estimate": cost,
                "error_rate_hint": 1.0 if error else 0.0,
                "model_tier": model_tier,
                "rate_limit_kind": rate_limit_kind,
                **{k: v for k, v in ctx.items() if v is not None},
            },
        }
    )


def record_pipeline_error(*, source_type: str, user_id: str, error: str) -> None:
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "source_type": source_type,
        "user_id": user_id,
        "error": error[:500],
    }
    def _persist_err(r: redis.Redis) -> None:
        key = "obs:pipeline:errors"
        r.lpush(key, json.dumps(row))
        r.ltrim(key, 0, 999)

    _redis_store(_persist_err)


def record_pipeline_run_trace(
    state: dict[str, Any],
    validated_tasks: list[dict],
    policy_version: str,
    *,
    provenance_summary: dict[str, Any] | None = None,
    evidence_stats: dict[str, Any] | None = None,
    calibration_info: dict[str, Any] | None = None,
) -> None:
    pv = str(state.get("policy_version") or policy_version or "unknown")
    counts = {"accept": 0, "uncertain": 0, "abstain": 0}
    for t in validated_tasks:
        if not isinstance(t, dict):
            continue
        b = t.get("decision_band")
        if b in counts:
            counts[b] += 1
    err_list = state.get("errors")
    errs = err_list if isinstance(err_list, list) else []
    normalize_fallback_used = any(
        isinstance(e, str) and ("normalize_tasks failed" in e or "fallback normalization" in e.lower()) for e in errs
    )

    prov = provenance_summary if isinstance(provenance_summary, dict) else {}
    llm_fallback_used = bool(prov.get("llm_fallback_used"))
    llm_calls_total = int(prov.get("llm_calls_total") or 0)
    llm_fallback_calls = int(prov.get("llm_fallback_calls") or 0)
    llm_rate_limited_calls = int(prov.get("llm_rate_limited_calls") or 0)
    llm_models = list(prov.get("llm_models") or [])

    ev = evidence_stats if isinstance(evidence_stats, dict) else {}
    evidence_tasks_with_quote = int(ev.get("tasks_with_quote") or 0)
    evidence_invalid_quote_drops = int(ev.get("invalid_quote_drops") or 0)
    evidence_coverage = (
        round(evidence_tasks_with_quote / len(validated_tasks), 4)
        if validated_tasks
        else None
    )

    cal = calibration_info if isinstance(calibration_info, dict) else {}
    calibration_applied = bool(cal.get("applied"))
    calibration_method = cal.get("method")
    calibration_version = cal.get("version")
    calibration_remapped = int(cal.get("remapped_count") or 0)

    row = {
        "ts": datetime.now(UTC).isoformat(),
        "policy_version": pv,
        "source_type": state.get("source_type"),
        "user_id": state.get("user_id"),
        "source_doc_id": state.get("source_doc_id"),
        "pipeline_run_id": state.get("pipeline_run_id"),
        "task_count": len(validated_tasks),
        "decision_counts": counts,
        "abstained": counts.get("abstain", 0),
        # `fallback_used` historically meant "did the normalize node hit its
        # fallback path?" — not "did the LLM route to the fallback model?".
        # Kept for back-compat under its accurate new name. The real LLM
        # routing signal is `llm_fallback_used` below, sourced from
        # per-call provenance and never from error-string sniffing.
        "fallback_used": normalize_fallback_used,
        "normalize_fallback_used": normalize_fallback_used,
        "llm_fallback_used": llm_fallback_used,
        "llm_calls_total": llm_calls_total,
        "llm_fallback_calls": llm_fallback_calls,
        "llm_rate_limited_calls": llm_rate_limited_calls,
        "llm_models": llm_models,
        "evidence_tasks_with_quote": evidence_tasks_with_quote,
        "evidence_invalid_quote_drops": evidence_invalid_quote_drops,
        "evidence_coverage": evidence_coverage,
        "calibration_applied": calibration_applied,
        "calibration_method": calibration_method,
        "calibration_version": calibration_version,
        "calibration_remapped": calibration_remapped,
        "deadline_v2_type": [(t.get("deadline_v2") or {}).get("type") if isinstance(t, dict) else None for t in validated_tasks],
        "uncertainty_type": [
            (t.get("uncertainty") or {}).get("type") if isinstance(t, dict) else None for t in validated_tasks
        ],
    }
    def _persist_run(r: redis.Redis) -> None:
        key = "obs:pipeline:runs"
        r.lpush(key, json.dumps(row))
        r.ltrim(key, 0, 499)

    _redis_store(_persist_run)

    if settings.langsmith_tracing and settings.langsmith_api_key:
        pin: dict[str, Any] = {"policy_version": pv, "source_type": state.get("source_type")}
        esid = state.get("eval_sample_id")
        if isinstance(esid, str) and esid.strip():
            pin["sample_id"] = esid.strip()
        rid = (os.getenv("EVAL_RUN_ID") or "").strip()
        if rid:
            pin["eval_run_id"] = rid
        _post_langsmith_run(
            {
                "id": str(uuid4()),
                "name": "pipeline_run_trace",
                "run_type": "chain",
                "session_name": _langsmith_session_name(),
                "inputs": pin,
                "outputs": {
                    "decision_counts": counts,
                    "abstained": counts.get("abstain", 0),
                    "fallback_used": normalize_fallback_used,
                    "normalize_fallback_used": normalize_fallback_used,
                    "llm_fallback_used": llm_fallback_used,
                    "llm_fallback_calls": llm_fallback_calls,
                    "llm_rate_limited_calls": llm_rate_limited_calls,
                    "evidence_coverage": evidence_coverage,
                    "evidence_invalid_quote_drops": evidence_invalid_quote_drops,
                    "calibration_applied": calibration_applied,
                    "calibration_method": calibration_method,
                    "calibration_version": calibration_version,
                },
                "start_time": row["ts"],
                "end_time": datetime.now(UTC).isoformat(),
                "extra": {
                    "deadline_v2_type": row["deadline_v2_type"],
                    "uncertainty_type": row["uncertainty_type"],
                    "task_count": len(validated_tasks),
                },
            }
        )


def _langsmith_ingest_snapshot() -> dict[str, Any]:
    if _redis_unavailable or not settings.redis_observability_enabled:
        return {}
    try:
        r = _redis_client()
        raw = r.hgetall("obs:langsmith:ingest:counts")
    except (redis.ConnectionError, redis.TimeoutError, OSError):
        return {}
    except Exception as exc:
        _warn_observability_once(
            "redis_langsmith_snapshot",
            "observability: cannot read LangSmith ingest counters from Redis (err=%s)",
            type(exc).__name__,
        )
        return {}
    if not raw:
        return {}
    counts = {k: int(v) for k, v in raw.items()}
    attempts = int(counts.get("attempts", 0))
    success = int(counts.get("success", 0))
    return {
        **counts,
        "failure_rate": round((attempts - success) / attempts, 4) if attempts else 0.0,
    }


def _empty_slo_snapshot() -> dict[str, Any]:
    ls_snap = _langsmith_ingest_snapshot()
    return {
        "sample_size": 0,
        "error_rate": 0.0,
        "p50_ms": 0,
        "p95_ms": 0,
        "p99_ms": 0,
        "cost_total": 0.0,
        "langsmith_ingest": ls_snap,
        "langsmith_post_fail_rate": ls_snap.get("failure_rate", 0.0),
    }


def calculate_slo_snapshot() -> dict[str, Any]:
    if _redis_unavailable or not settings.redis_observability_enabled:
        return _empty_slo_snapshot()
    try:
        r = _redis_client()
        rows = r.lrange("obs:llm:calls", 0, 999)
    except (redis.ConnectionError, redis.TimeoutError, OSError):
        return _empty_slo_snapshot()
    except Exception as exc:
        _warn_observability_once(
            "redis_slo_snapshot",
            "observability: cannot read SLO telemetry from Redis (err=%s)",
            type(exc).__name__,
        )
        return _empty_slo_snapshot()

    calls = []
    for raw in rows:
        try:
            calls.append(json.loads(raw))
        except Exception:
            continue
    if not calls:
        return _empty_slo_snapshot()

    lats = sorted(float(c.get("latency_ms") or 0) for c in calls)
    errors = sum(1 for c in calls if c.get("error"))
    cost_total = round(sum(float(c.get("cost_estimate") or 0) for c in calls), 8)

    tier_counts: dict[str, int] = {}
    rl_kind_counts: dict[str, int] = {}
    fallback_calls = 0
    for c in calls:
        tier = c.get("model_tier") or "unknown"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if tier == "fallback":
            fallback_calls += 1
        kind = c.get("rate_limit_kind")
        if kind:
            rl_kind_counts[kind] = rl_kind_counts.get(kind, 0) + 1

    def pct(p: float) -> float:
        if not lats:
            return 0.0
        idx = int((len(lats) - 1) * p)
        return round(lats[idx], 2)

    ls_snap = _langsmith_ingest_snapshot()
    return {
        "sample_size": len(calls),
        "error_rate": round(errors / len(calls), 4),
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "cost_total": cost_total,
        # Fallback usage is a first-class SLO signal: a spike here means the
        # primary model is cooking, quality degrades, and eval metrics get
        # contaminated by a weaker model. Surfacing it explicitly (rather than
        # requiring callers to re-parse obs records) prevents silent drift.
        "fallback_call_rate": round(fallback_calls / len(calls), 4),
        "tier_counts": tier_counts,
        "rate_limit_kind_counts": rl_kind_counts,
        "checked_at": datetime.now(UTC).isoformat(),
        "slo_targets": {"p50_lt_ms": 3000, "p95_lt_ms": 10000, "p99_lt_ms": 20000},
        "langsmith_ingest": ls_snap,
        # Convenience alias so callers don't need to dig into the nested dict.
        "langsmith_post_fail_rate": ls_snap.get("failure_rate", 0.0),
    }
