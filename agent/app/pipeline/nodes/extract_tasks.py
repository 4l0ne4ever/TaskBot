import json
from difflib import SequenceMatcher

from app.pipeline.llm import call_llm
from app.pipeline.prompts import EXTRACTION_RETRY_HINT_V1, EXTRACTION_SYSTEM_V1, EXTRACTION_USER_V1
from app.pipeline.state import PipelineState

MAX_RETRIES = 3


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _validate_extraction_item(item: dict) -> bool:
    title = item.get("title")
    return isinstance(title, str) and 0 < len(title.strip()) <= 200


def parse_extraction_response(raw: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("tasks") or parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list):
        return []
    cleaned: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not _validate_extraction_item(item):
            continue
        cleaned.append(
            {
                "title": item.get("title"),
                "assignee_raw": item.get("assignee_raw"),
                "deadline_raw": item.get("deadline_raw"),
                "priority_raw": item.get("priority_raw"),
            }
        )
    return cleaned


def _merge_extracted_tasks(chunks_results: list[list[dict]]) -> list[dict]:
    merged: list[dict] = []
    for tasks in chunks_results:
        for task in tasks:
            title = str(task.get("title") or "")
            if not any(_similar(title, str(existing.get("title") or "")) > 0.85 for existing in merged):
                merged.append(task)
    return merged


def _build_extraction_prompt(state: PipelineState, text: str, with_retry_hint: bool = False) -> str:
    metadata = state.get("metadata") or {}
    prompt = EXTRACTION_SYSTEM_V1 + "\n\n" + EXTRACTION_USER_V1.format(
        text=text,
        source_type=state.get("source_type"),
        sender=metadata.get("sender"),
        sent_at=metadata.get("sent_at"),
    )
    if with_retry_hint:
        prompt = prompt + "\n\n" + EXTRACTION_RETRY_HINT_V1
    return prompt


def _extract_with_retry(state: PipelineState, text: str) -> tuple[list[dict], str | None]:
    for attempt in range(MAX_RETRIES):
        raw = call_llm(
            _build_extraction_prompt(state, text, with_retry_hint=attempt > 0),
            temperature=0.0,
        )
        tasks = parse_extraction_response(raw)
        if tasks:
            return tasks, None
    return [], "extract_tasks failed: no valid tasks after 3 attempts"


def extract_tasks(state: PipelineState) -> dict:
    errors = list(state.get("errors", []))
    chunks = state.get("chunks") or []
    cleaned_text = state.get("cleaned_text") or ""

    targets = chunks if chunks else ([cleaned_text] if cleaned_text else [])
    if not targets:
        return {"extracted_tasks": [], "errors": errors}

    all_chunk_results: list[list[dict]] = []
    for text in targets:
        tasks, error = _extract_with_retry(state, text)
        if error:
            errors.append(error)
        all_chunk_results.append(tasks)

    merged = _merge_extracted_tasks(all_chunk_results)
    return {"extracted_tasks": merged, "errors": errors}
