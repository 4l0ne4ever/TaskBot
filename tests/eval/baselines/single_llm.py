"""
Baseline 2 — Single LLM call extraction (no multi-stage pipeline).

One prompt that extracts + normalizes + detects conflicts in a single pass.
Primary: llama-3.3-70b-versatile, fallback: llama-3.1-8b-instant on rate limit.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from groq import Groq

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "agent"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

PRIMARY_MODEL = os.getenv("EVAL_GROQ_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = os.getenv("EVAL_GROQ_FALLBACK", "llama-3.1-8b-instant")
_client = Groq(api_key=os.environ["GROQ_API_KEY"])

_primary_calls = 0
_fallback_calls = 0

SINGLE_PASS_PROMPT = """You are a task extraction and normalization assistant.

Given the input text and metadata, do ALL of the following in one pass:
1. Extract every explicit work task or action item.
2. Normalize each task (resolve deadlines to ISO dates, clean assignee names).
3. Detect conflicts if multiple sources mention the same deliverable with different deadlines or assignees.

Return a JSON object with:
{{
  "tasks": [
    {{
      "title": "concise task description (max 80 chars)",
      "assignee": "name or null",
      "deadline": "YYYY-MM-DD or null",
      "priority": "high|medium|low or null"
    }}
  ],
  "conflicts": [
    {{
      "type": "deadline_conflict|assignee_conflict",
      "task_title": "which task",
      "source_a_value": "...",
      "source_b_value": "..."
    }}
  ]
}}

If no tasks found, return {{"tasks": [], "conflicts": []}}.

Reference date: {sent_at}

Text:
{text}
"""

_RPM_INTERVAL = 2.2


def _wait_from_error(exc_str: str) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", exc_str)
    if m:
        return float(m.group(1)) + 1
    m = re.search(r"try again in (\d+)m", exc_str)
    if m:
        return float(m.group(1)) * 60 + 5
    return 15


def _call(prompt: str, model: str) -> str:
    resp = _client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content if resp.choices else "[]"


def _call_with_fallback(prompt: str) -> str:
    global _primary_calls, _fallback_calls
    try:
        result = _call(prompt, PRIMARY_MODEL)
        _primary_calls += 1
        return result
    except Exception as exc:
        exc_str = str(exc)
        if "429" not in exc_str and "rate_limit" not in exc_str:
            raise
        wait = _wait_from_error(exc_str)
        if wait > 120 and FALLBACK_MODEL:
            _fallback_calls += 1
            return _call(prompt, FALLBACK_MODEL)
        time.sleep(min(wait, 30))
        try:
            result = _call(prompt, PRIMARY_MODEL)
            _primary_calls += 1
            return result
        except Exception:
            _fallback_calls += 1
            return _call(prompt, FALLBACK_MODEL)


def get_model_stats() -> dict:
    return {
        "primary_model": PRIMARY_MODEL,
        "fallback_model": FALLBACK_MODEL,
        "primary_calls": _primary_calls,
        "fallback_calls": _fallback_calls,
    }


def extract_single_llm(text: str, metadata: dict) -> dict:
    time.sleep(_RPM_INTERVAL)

    sent_at = metadata.get("sent_at", "2026-03-30")
    prompt = SINGLE_PASS_PROMPT.format(text=text, sent_at=sent_at)

    raw = None
    for attempt in range(5):
        try:
            raw = _call_with_fallback(prompt)
            break
        except Exception as exc:
            exc_str = str(exc)
            if "429" in exc_str or "rate_limit" in exc_str:
                wait = _wait_from_error(exc_str)
                print(f"    rate-limited on both models, waiting {wait:.0f}s (attempt {attempt+1})...", flush=True)
                time.sleep(wait)
            else:
                raise
    if raw is None:
        return {"tasks": [], "conflicts": [], "missing_fields": []}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"tasks": [], "conflicts": [], "missing_fields": []}

    if not isinstance(parsed, dict):
        return {"tasks": [], "conflicts": [], "missing_fields": []}

    tasks = parsed.get("tasks") or []
    if not isinstance(tasks, list):
        tasks = []
    tasks = [t for t in tasks if isinstance(t, dict) and t.get("title")]

    conflicts = parsed.get("conflicts") or []
    if not isinstance(conflicts, list):
        conflicts = []

    missing = []
    if tasks:
        if not any(t.get("deadline") for t in tasks):
            missing.append("deadline")
        if not any(t.get("assignee") for t in tasks):
            missing.append("assignee")

    return {"tasks": tasks, "conflicts": conflicts, "missing_fields": missing}
