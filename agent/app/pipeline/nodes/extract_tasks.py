import json
import re

from app.config import get_settings
from app.pipeline.llm import call_llm, llm_call_context
from app.pipeline.policy import get_pipeline_policy
from app.pipeline.prompts import (
    EXTRACTION_RETRY_HINT_V1,
    EXTRACTION_SYSTEM_SENT,
    EXTRACTION_SYSTEM_V1,
    EXTRACTION_USER_V1,
)
from app.pipeline.state import PipelineState

settings = get_settings()


def _title_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def _canonical_title(text: str) -> str:
    return " ".join(_title_tokens(text))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _mergeable_titles(a: str, b: str) -> bool:
    ca = _canonical_title(a)
    cb = _canonical_title(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    ta = _title_tokens(a)
    tb = _title_tokens(b)
    if not ta or not tb:
        return False
    # Guardrail: only merge if first action verb token matches.
    if ta[0] != tb[0]:
        return False
    # Strong similarity for near-duplicates only.
    return _jaccard(set(ta), set(tb)) >= settings.extract_merge_jaccard_threshold


def _compatible_field(a: object, b: object) -> bool:
    av = str(a or "").strip().lower()
    bv = str(b or "").strip().lower()
    if not av or not bv:
        return True
    return av == bv


def _merge_task_items(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    # Keep richer title/description when possible.
    if len(str(incoming.get("title") or "")) > len(str(merged.get("title") or "")):
        merged["title"] = incoming.get("title")
    for key in ("assignee", "deadline", "priority"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming.get(key)
    if not merged.get("source_ref") and incoming.get("source_ref"):
        merged["source_ref"] = incoming.get("source_ref")
    if not merged.get("deadline_v2") and isinstance(incoming.get("deadline_v2"), dict):
        merged["deadline_v2"] = incoming.get("deadline_v2")
    if not merged.get("uncertainty") and isinstance(incoming.get("uncertainty"), dict):
        merged["uncertainty"] = incoming.get("uncertainty")
    if not merged.get("confidence") and incoming.get("confidence") is not None:
        merged["confidence"] = incoming.get("confidence")
    if not merged.get("evidence_quote") and isinstance(incoming.get("evidence_quote"), str):
        merged["evidence_quote"] = incoming.get("evidence_quote")
    return merged


def _can_merge_tasks(a: dict, b: dict) -> bool:
    at = str(a.get("title") or "")
    bt = str(b.get("title") or "")
    if not _mergeable_titles(at, bt):
        return False
    if not _compatible_field(a.get("assignee"), b.get("assignee")):
        return False
    if not _compatible_field(
        (a.get("deadline_v2") or {}).get("text"),
        (b.get("deadline_v2") or {}).get("text"),
    ):
        return False
    return True


def _validate_extraction_item(item: dict) -> bool:
    title = item.get("title")
    return isinstance(title, str) and 0 < len(title.strip()) <= 200


def _structural_item_count(text: str) -> int:
    """Count visible list/thread item rows as a lower-bound coverage hint.

    This is deliberately structural (line markers and labels), not a semantic
    keyword list. It only drives a retry when the LLM returns fewer tasks than
    the document's visible item structure suggests, reducing missed last-item
    failures without inventing tasks itself.
    """
    count = 0
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+[.)]\s+\S", stripped):
            count += 1
            continue
        if re.match(r"^[-*•]\s+\S", stripped):
            count += 1
            continue
        if re.match(r"^\[[^\]]+\]\s*$", stripped):
            count += 1
            continue
    max_tasks = max(1, int(settings.max_tasks_per_document))
    return min(count, max_tasks)


def parse_extraction_response(raw: str) -> list[dict]:
    raw = _repair_jsonish(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        if "tasks" in parsed and isinstance(parsed["tasks"], list):
            parsed = parsed["tasks"]
        else:
            parsed = parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list):
        return []
    cleaned: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not _validate_extraction_item(item):
            continue
        eq = item.get("evidence_quote")
        cleaned.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                "assignee": item.get("assignee"),
                "source_ref": item.get("source_ref") if isinstance(item.get("source_ref"), str) else None,
                "deadline": item.get("deadline"),
                "deadline_v2": item.get("deadline_v2") if isinstance(item.get("deadline_v2"), dict) else None,
                "priority": item.get("priority"),
                "confidence": item.get("confidence"),
                "uncertainty": item.get("uncertainty") if isinstance(item.get("uncertainty"), dict) else None,
                "evidence_quote": eq if isinstance(eq, str) else None,
            }
        )
    return cleaned


def _strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _balanced_json_slice(text: str) -> str:
    start_positions = [p for p in (text.find("{"), text.find("[")) if p >= 0]
    if not start_positions:
        return text
    start = min(start_positions)
    stack: list[str] = []
    in_str = False
    esc = False
    for i, ch in enumerate(text[start:], start=start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack and ch == stack[-1]:
                stack.pop()
                if not stack:
                    return text[start : i + 1]
            else:
                break
    return text[start:]


def _repair_jsonish(raw: str) -> str:
    """Best-effort syntactic cleanup before spending another LLM call.

    Groq JSON mode already helps, but operational traces showed parse failures
    still causing full retries. This layer handles provider-agnostic wrappers
    and common JSON syntax slips (markdown fences, prose around JSON, trailing
    commas) while leaving semantic validation to ``parse_extraction_response``.
    """
    text = _balanced_json_slice(_strip_code_fence(raw))
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()


def _compact_tasks(tasks: list[dict]) -> list[dict]:
    unique: list[dict] = []
    for task in tasks:
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        merged_index = None
        for idx, existing in enumerate(unique):
            if _can_merge_tasks(existing, task):
                merged_index = idx
                break
        if merged_index is not None:
            unique[merged_index] = _merge_task_items(unique[merged_index], task)
            continue
        unique.append(task)
        if len(unique) >= settings.max_tasks_per_document:
            break
    return unique


def _merge_extracted_tasks(chunks_results: list[list[dict]]) -> list[dict]:
    merged: list[dict] = []
    for tasks in chunks_results:
        for task in tasks:
            merged_index = None
            for idx, existing in enumerate(merged):
                if _can_merge_tasks(existing, task):
                    merged_index = idx
                    break
            if merged_index is None:
                merged.append(task)
            else:
                merged[merged_index] = _merge_task_items(merged[merged_index], task)
    return merged


def _build_extraction_prompt(
    state: PipelineState, text: str, with_retry_hint: bool = False
) -> tuple[str, str]:
    metadata = state.get("metadata") or {}
    policy = get_pipeline_policy()
    guidance = (policy.extraction_guidance or "").strip()
    guidance_block = f"Policy guidance:\n{guidance}\n" if guidance else ""
    prompt_body = EXTRACTION_USER_V1
    prompt_body = prompt_body.replace("{text}", str(text))
    prompt_body = prompt_body.replace("{source_type}", str(state.get("source_type")))
    prompt_body = prompt_body.replace("{sender}", str(metadata.get("sender")))
    prompt_body = prompt_body.replace("{sent_at}", str(metadata.get("sent_at")))
    prompt_body = prompt_body.replace("{subject}", str(metadata.get("subject")))
    prompt_body = prompt_body.replace("{extraction_guidance}", guidance_block)
    # Round 11 (2026-05-30): sent-folder mail uses an inverted assignee
    # default (the current user is the *assignor*, not the assignee). Route
    # to the SENT system prompt when the queue-consumer-supplied
    # ``metadata.folder`` says so. Default remains the inbox/V1 prompt for
    # every other source — Drive, uploads, and inbox-gmail are all
    # received-by-the-user contexts where the V1 assignee-default applies.
    system_prompt = (
        EXTRACTION_SYSTEM_SENT
        if str(metadata.get("folder") or "").lower() == "sent"
        else EXTRACTION_SYSTEM_V1
    )
    user_prompt = prompt_body
    if with_retry_hint:
        user_prompt = user_prompt + "\n\n" + EXTRACTION_RETRY_HINT_V1
    return system_prompt, user_prompt


def _extract_with_retry(
    state: PipelineState,
    text: str,
    *,
    chunk_index: int,
    chunk_count: int,
) -> tuple[list[dict], str | None]:
    retries = max(1, int(settings.extraction_max_retries))
    retry_cap = max(1000, int(settings.llm_retry_truncate_chars))
    retry_factor = float(settings.llm_retry_truncate_factor)
    if retry_factor <= 0 or retry_factor >= 1:
        retry_factor = 0.7
    for attempt in range(retries):
        retry_text = text
        if attempt > 0 and len(retry_text) > retry_cap:
            budget = max(1000, int(retry_cap * (retry_factor ** (attempt - 1))))
            retry_text = retry_text[:budget]
        system_prompt, user_prompt = _build_extraction_prompt(
            state, retry_text, with_retry_hint=attempt > 0
        )
        with llm_call_context(
            node_name="extract_tasks",
            call_purpose="extract",
            retry_attempt=attempt,
            chunk_index=chunk_index,
            chunk_count=chunk_count,
        ):
            raw = call_llm(
                user_prompt,
                temperature=0.0,
                system_prompt=system_prompt,
                max_tokens=max(128, int(settings.llm_extract_max_tokens)),
            )
        tasks = parse_extraction_response(raw)
        if tasks:
            minimum_items = _structural_item_count(retry_text)
            if minimum_items and len(tasks) < minimum_items and attempt < retries - 1:
                continue
            return tasks, None
    return [], f"extract_tasks failed: no valid tasks after {retries} attempts"


def extract_tasks(state: PipelineState) -> dict:
    errors = list(state.get("errors", []))
    chunks = state.get("chunks") or []
    cleaned_text = state.get("cleaned_text") or ""

    targets = chunks if chunks else ([cleaned_text] if cleaned_text else [])
    if not targets:
        return {"extracted_tasks": [], "errors": errors}

    all_chunk_results: list[list[dict]] = []
    total_targets = len(targets)
    for idx, text in enumerate(targets):
        tasks, error = _extract_with_retry(state, text, chunk_index=idx, chunk_count=total_targets)
        if error:
            errors.append(error)
        all_chunk_results.append(tasks)

    merged = _merge_extracted_tasks(all_chunk_results)
    compacted = _compact_tasks(merged)
    return {"extracted_tasks": compacted, "errors": errors}
