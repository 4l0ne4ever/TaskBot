import json
from datetime import date, datetime

from app.pipeline.llm import call_llm
from app.pipeline.prompts import NORMALIZATION_USER_V1
from app.pipeline.state import PipelineState

MAX_RETRIES = 3


def _normalize_priority(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    if text in {"high", "urgent", "asap", "critical"}:
        return "high"
    if text in {"medium", "normal"}:
        return "medium"
    if text in {"low"}:
        return "low"
    return None


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _fallback_normalize(tasks: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for task in tasks:
        deadline_raw = task.get("deadline_raw")
        normalized.append(
            {
                "title": task.get("title"),
                "assignee": task.get("assignee_raw"),
                "deadline": deadline_raw if isinstance(deadline_raw, str) and _is_iso_date(deadline_raw) else None,
                "priority": _normalize_priority(task.get("priority_raw")),
            }
        )
    return normalized


def _parse_normalization_response(raw: str, input_len: int) -> list[dict]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("tasks") or parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list) or len(parsed) != input_len:
        return []
    result: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            return []
        deadline = item.get("deadline")
        if deadline is not None and (not isinstance(deadline, str) or not _is_iso_date(deadline)):
            return []
        priority = item.get("priority")
        if priority not in {"high", "medium", "low", None}:
            return []
        result.append(
            {
                "title": item.get("title"),
                "assignee": item.get("assignee"),
                "deadline": deadline,
                "priority": priority,
            }
        )
    return result


def normalize_tasks(state: PipelineState) -> dict:
    extracted = state.get("extracted_tasks", [])
    errors = list(state.get("errors", []))
    if not extracted:
        return {"normalized_tasks": [], "errors": errors}

    metadata = state.get("metadata") or {}
    sent_at = metadata.get("sent_at")
    reference_date = datetime.now().date().isoformat()
    if isinstance(sent_at, str) and sent_at:
        reference_date = sent_at[:10]

    prompt = NORMALIZATION_USER_V1.format(
        reference_date=reference_date,
        tasks_json=json.dumps(extracted, ensure_ascii=True),
    )

    for _ in range(MAX_RETRIES):
        raw = call_llm(prompt, temperature=0.0)
        normalized = _parse_normalization_response(raw, len(extracted))
        if normalized:
            return {"normalized_tasks": normalized, "errors": errors}

    errors.append("normalize_tasks failed: fallback normalization applied")
    return {"normalized_tasks": _fallback_normalize(extracted), "errors": errors}
