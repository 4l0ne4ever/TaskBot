"""
Method 3 — Multi-stage LangGraph pipeline extraction.

Runs the full pipeline (parse_input -> extract -> normalize -> validate)
with mock save/dispatch to avoid DB/MCP side effects.

Uses EVAL_GROQ_MODEL, else GROQ_MODEL, else the pydantic default for Settings.groq_model (app.config).
"""
from __future__ import annotations

import os
import re
import sys
import time
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "agent"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.config import Settings, get_settings  # noqa: E402

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "GMAIL_MCP_URL",
    "DRIVE_MCP_URL",
    "CALENDAR_MCP_URL",
    "BACKEND_API_BASE_URL",
]
missing_env = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
if missing_env:
    raise RuntimeError(f"Missing required env vars for pipeline eval: {', '.join(missing_env)}")


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


# Single primary model (default Settings.groq_model / gpt-oss-120b): no Llama/Gemini hops; pairs with
# run_eval EVAL_ABORT_ON_DAILY_QUOTA partial JSON + --resume after quota reset.
if _env_truthy("EVAL_STRICT_PRIMARY_MODEL_ONLY"):
    _oss = str(Settings.model_fields["groq_model"].default)
    os.environ["GROQ_STRICT_PRIMARY"] = "1"
    os.environ["GROQ_DISABLE_GEMINI_FALLBACK"] = "1"
    os.environ["GROQ_MODEL"] = _oss
    os.environ["EVAL_GROQ_MODEL"] = _oss
    print(
        "EVAL_STRICT_PRIMARY_MODEL_ONLY: strict Groq primary, no Gemini fallback, "
        f"model={_oss}",
        flush=True,
    )

# Resolution: EVAL_GROQ_MODEL → GROQ_MODEL → pydantic default on Settings.groq_model (app.config).
_EVAL_GROQ_FALLBACK = str(Settings.model_fields["groq_model"].default)
EVAL_MODEL = (
    os.getenv("EVAL_GROQ_MODEL")
    or os.getenv("GROQ_MODEL")
    or _EVAL_GROQ_FALLBACK
)
if EVAL_MODEL:
    os.environ["GROQ_MODEL"] = EVAL_MODEL

# Invalidate cached Settings so llm/observability see GROQ_MODEL from above (import order safe).
get_settings.cache_clear()

_gemini_eval = bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())

# Routing matches production (agent/app/pipeline/llm.py): Groq primary → Groq fallback → Gemini.
# Do not override GROQ_STRICT_PRIMARY here — set it in .env only when you need Groq-primary-only
# measurement (no fallback/Gemini hops).

# Gemini-only sweep: strict + EVAL_GEMINI_ONLY so call_llm pins Gemini when configured.
if (os.getenv("EVAL_GEMINI_ONLY") or "").strip().lower() in {"1", "true", "yes", "on"} and _gemini_eval:
    os.environ["GROQ_STRICT_PRIMARY"] = "1"

get_settings.cache_clear()

_patched = False


def _ensure_patched():
    global _patched
    if _patched:
        return
    save_mod = import_module("app.pipeline.nodes.save_tasks")
    dispatch_mod = import_module("app.pipeline.nodes.dispatch_notifications")

    save_mod.save_tasks_sync = lambda state: {"saved_task_ids": [], "errors": list(state.get("errors", []))}
    dispatch_mod.dispatch_notifications_sync = lambda state: {"notifications_sent": [], "errors": list(state.get("errors", []))}
    _patched = True


_RPM_INTERVAL = float(os.getenv("EVAL_RPM_INTERVAL_SECONDS", "12.0"))
_MAX_RETRIES = 5
_MAX_WAIT_SECONDS = float(os.getenv("EVAL_MAX_RATE_LIMIT_WAIT_SECONDS", "30"))


def _wait_from_error(exc_str: str) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", exc_str)
    if m:
        return float(m.group(1)) + 1
    m = re.search(r"try again in (\d+)m", exc_str)
    if m:
        return float(m.group(1)) * 60 + 5
    return 20


def _is_daily_quota_error(exc_str: str) -> bool:
    """Detect a Groq TPD/RPD 429 (daily budget exhausted).

    Daily quotas only reset at midnight UTC, so retrying in-process is a
    guaranteed waste: the sweep log from 2026-04-18 shows five sequential
    ``try again in 845s`` retries per sample, eating ~2.5 min of wall clock
    for each doomed sample. Fail fast instead — the eval harness already
    records these as runtime errors and continues with the next sample,
    which is the outcome we actually want for forensic sweeps.
    """

    t = exc_str.lower()
    return "tokens per day" in t or "(tpd)" in t or "requests per day" in t or "(rpd)" in t


def extract_pipeline(
    text: str,
    metadata: dict,
    *,
    existing_tasks: list[dict] | None = None,
    trace_sample_id: str | None = None,
) -> dict:
    time.sleep(_RPM_INTERVAL)

    get_settings.cache_clear()
    import app.pipeline.llm as llm_mod

    llm_mod.settings = get_settings()
    _ensure_patched()
    from app.pipeline.graph import pipeline
    from app.pipeline.llm import collect_provenance

    sent_at = metadata.get("sent_at", "2026-03-30")
    sender = metadata.get("sender")
    subject = metadata.get("subject")

    existing = existing_tasks if isinstance(existing_tasks, list) else []

    tid = (trace_sample_id or "").strip()
    prev_trace = os.environ.get("EVAL_TRACE_SAMPLE_ID")
    if tid:
        os.environ["EVAL_TRACE_SAMPLE_ID"] = tid

    state = {
        "user_id": "eval-user",
        "access_token": "tok",
        "source_doc_id": "eval-doc",
        "source_type": "gmail",
        "raw_content": text,
        "metadata": {"sender": sender, "sent_at": sent_at, "subject": subject},
        "errors": [],
        "should_stop": False,
        "existing_tasks": existing,
        "eval_sample_id": tid,
    }

    last_err = None
    call_records: list = []
    try:
        with collect_provenance() as records:
            for attempt in range(_MAX_RETRIES):
                try:
                    result = pipeline.invoke(state)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    exc_str = str(exc)
                    if "429" in exc_str or "rate_limit" in exc_str:
                        if _is_daily_quota_error(exc_str):
                            # Don't burn wall clock on a quota that resets at
                            # 00:00 UTC. Re-raise so the eval harness records
                            # one runtime error and moves to the next sample.
                            print(
                                "    pipeline daily quota (TPD/RPD) hit — failing fast",
                                flush=True,
                            )
                            raise
                        wait = _wait_from_error(exc_str)
                        bounded_wait = min(wait, _MAX_WAIT_SECONDS)
                        print(
                            f"    pipeline rate-limited, waiting {bounded_wait:.0f}s "
                            f"(raw={wait:.0f}s, attempt {attempt+1})...",
                            flush=True,
                        )
                        time.sleep(bounded_wait)
                    else:
                        raise
            if last_err is not None:
                raise last_err
            call_records = list(records)
    finally:
        if tid:
            if prev_trace is None:
                os.environ.pop("EVAL_TRACE_SAMPLE_ID", None)
            else:
                os.environ["EVAL_TRACE_SAMPLE_ID"] = prev_trace

    tasks = result.get("validated_tasks") or result.get("normalized_tasks") or result.get("extracted_tasks") or []
    conflicts = result.get("conflicts") or []

    candidate_tasks = []
    clean_tasks = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("superseded_by"):
            continue
        row = {
            "title": t.get("title", ""),
            "assignee": t.get("assignee"),
            "assignee_canonical": t.get("assignee_canonical"),
            "deadline": t.get("deadline"),
            "priority": t.get("priority"),
        }
        if t.get("confidence") is not None:
            row["confidence"] = t.get("confidence")
        if t.get("raw_confidence") is not None:
            row["raw_confidence"] = t.get("raw_confidence")
        if t.get("decision_score") is not None:
            row["decision_score"] = t.get("decision_score")
        if t.get("decision_band") is not None:
            row["decision_band"] = t.get("decision_band")
        row["abstained"] = bool(t.get("abstained"))
        candidate_tasks.append(row)
        if not row["abstained"]:
            clean_tasks.append(row)

    clean_conflicts = []
    for c in conflicts:
        if not isinstance(c, dict):
            continue
        # Preserve Phase 2 scope tagging + source refs so downstream eval
        # comparisons can verify thread_update / multi_source detection. The
        # legacy 3-key shape (type / task_title / description) is preserved
        # for back-compat with older reports.
        clean_conflicts.append({
            "type": c.get("conflict_type", ""),
            "task_title": c.get("task_title", ""),
            "description": c.get("description"),
            "scope": c.get("scope"),
            "source_a_ref": c.get("source_a_ref"),
            "source_b_ref": c.get("source_b_ref"),
        })

    missing = []
    if clean_tasks:
        if not any(t.get("deadline") for t in clean_tasks):
            missing.append("deadline")
        if not any(t.get("assignee") for t in clean_tasks):
            missing.append("assignee")

    models_used: dict[str, int] = {}
    primary_calls = 0
    fallback_calls = 0
    rate_limited_calls = 0
    for rec in call_records:
        model_name = getattr(rec, "model", None) or "unknown"
        models_used[model_name] = models_used.get(model_name, 0) + 1
        if getattr(rec, "is_fallback", False):
            fallback_calls += 1
        else:
            primary_calls += 1
        if getattr(rec, "rate_limited", False):
            rate_limited_calls += 1
    provenance = {
        "primary_calls": primary_calls,
        "fallback_calls": fallback_calls,
        "rate_limited_calls": rate_limited_calls,
        "models_used": models_used,
        "contaminated": fallback_calls > 0,
    }

    return {
        "tasks": clean_tasks,
        "conflicts": clean_conflicts,
        "missing_fields": missing,
        "_meta": {
            "model_provenance": provenance,
            "candidate_tasks": candidate_tasks,
            "candidate_task_count": len(candidate_tasks),
            "scored_task_count": len(clean_tasks),
        },
    }
