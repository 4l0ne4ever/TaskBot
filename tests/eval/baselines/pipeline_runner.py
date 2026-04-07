"""
Method 3 — Multi-stage LangGraph pipeline extraction.

Runs the full pipeline (parse_input -> extract -> normalize -> validate)
with mock save/dispatch to avoid DB/MCP side effects.

Uses EVAL_GROQ_MODEL env var to override the model for eval runs.
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

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://taskbot:taskbot@localhost:5432/taskbot")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GMAIL_MCP_URL", "https://gmail-mcp.local/mcp")
os.environ.setdefault("DRIVE_MCP_URL", "https://drive-mcp.local/mcp")
os.environ.setdefault("CALENDAR_MCP_URL", "https://calendar-mcp.local/mcp")
os.environ.setdefault("BACKEND_API_BASE_URL", "http://127.0.0.1:8000")

EVAL_MODEL = os.getenv("EVAL_GROQ_MODEL", "llama-3.3-70b-versatile")
EVAL_FALLBACK = os.getenv("EVAL_GROQ_FALLBACK", "llama-3.1-8b-instant")
if EVAL_MODEL:
    os.environ["GROQ_MODEL"] = EVAL_MODEL
if EVAL_FALLBACK:
    os.environ["GROQ_FALLBACK_MODEL"] = EVAL_FALLBACK

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


_RPM_INTERVAL = 4.0
_MAX_RETRIES = 5


def _wait_from_error(exc_str: str) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", exc_str)
    if m:
        return float(m.group(1)) + 1
    m = re.search(r"try again in (\d+)m", exc_str)
    if m:
        return float(m.group(1)) * 60 + 5
    return 20


def extract_pipeline(text: str, metadata: dict) -> dict:
    time.sleep(_RPM_INTERVAL)

    _ensure_patched()
    from app.pipeline.graph import pipeline

    sent_at = metadata.get("sent_at", "2026-03-30")
    sender = metadata.get("sender")
    subject = metadata.get("subject")

    state = {
        "user_id": "eval-user",
        "access_token": "tok",
        "source_doc_id": "eval-doc",
        "source_type": "gmail",
        "raw_content": text,
        "metadata": {"sender": sender, "sent_at": sent_at, "subject": subject},
        "errors": [],
        "should_stop": False,
        "existing_tasks": [],
    }

    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            result = pipeline.invoke(state)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            exc_str = str(exc)
            if "429" in exc_str or "rate_limit" in exc_str:
                wait = _wait_from_error(exc_str)
                print(f"    pipeline rate-limited, waiting {wait:.0f}s (attempt {attempt+1})...", flush=True)
                time.sleep(wait)
            else:
                raise
    if last_err is not None:
        raise last_err

    tasks = result.get("validated_tasks") or result.get("normalized_tasks") or result.get("extracted_tasks") or []
    conflicts = result.get("conflicts") or []

    clean_tasks = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        clean_tasks.append({
            "title": t.get("title", ""),
            "assignee": t.get("assignee"),
            "deadline": t.get("deadline"),
            "priority": t.get("priority"),
        })

    clean_conflicts = []
    for c in conflicts:
        if not isinstance(c, dict):
            continue
        clean_conflicts.append({
            "type": c.get("conflict_type", ""),
            "task_title": c.get("task_title", ""),
            "description": c.get("description"),
        })

    missing = []
    if clean_tasks:
        if not any(t.get("deadline") for t in clean_tasks):
            missing.append("deadline")
        if not any(t.get("assignee") for t in clean_tasks):
            missing.append("assignee")

    return {"tasks": clean_tasks, "conflicts": clean_conflicts, "missing_fields": missing}
