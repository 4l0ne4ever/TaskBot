import json

from app.pipeline.llm import call_llm
from app.pipeline.prompts import CONFLICT_USER_V1
from app.pipeline.state import PipelineState
from app.services.existing_tasks_loader import load_existing_tasks_for_validate_sync
from app.services.task_dedupe import title_similarity

MAX_CONFLICT_CHECKS_PER_TASK = 5
TITLE_SIMILARITY_THRESHOLD = 0.7


def _missing_fields(task: dict) -> list[str]:
    missing: list[str] = []
    if not task.get("deadline"):
        missing.append("deadline")
    if not task.get("assignee"):
        missing.append("assignee")
    return missing


def _parse_conflict_response(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"conflict_type": "no_conflict", "description": None}
    if not isinstance(parsed, dict):
        return {"conflict_type": "no_conflict", "description": None}
    conflict_type = parsed.get("conflict_type")
    if conflict_type not in {"deadline_conflict", "assignee_conflict", "no_conflict"}:
        conflict_type = "no_conflict"
    description = parsed.get("description")
    if description is not None and not isinstance(description, str):
        description = None
    return {"conflict_type": conflict_type, "description": description}


def _get_existing_tasks(state: PipelineState) -> list[dict]:
    if "existing_tasks" in state:
        raw = state.get("existing_tasks")
        return raw if isinstance(raw, list) else []
    return load_existing_tasks_for_validate_sync(state)


def _build_conflicts_for_task(task: dict, candidates: list[dict]) -> list[dict]:
    conflicts: list[dict] = []
    checks = 0
    for existing in candidates:
        if checks >= MAX_CONFLICT_CHECKS_PER_TASK:
            break
        checks += 1
        raw = call_llm(
            CONFLICT_USER_V1.format(
                task_a_json=json.dumps(task, ensure_ascii=True),
                task_b_json=json.dumps(existing, ensure_ascii=True),
            ),
            temperature=0.0,
        )
        parsed = _parse_conflict_response(raw)
        if parsed["conflict_type"] == "no_conflict":
            continue
        conflicts.append(
            {
                "conflict_type": parsed["conflict_type"],
                "description": parsed["description"],
                "source_a_ref": task.get("source_ref"),
                "source_b_ref": existing.get("source_ref") or existing.get("id"),
                "task_title": task.get("title"),
            }
        )
    return conflicts


def validate_tasks(state: PipelineState) -> dict:
    normalized = state.get("normalized_tasks", [])
    errors = list(state.get("errors", []))
    existing_tasks = _get_existing_tasks(state)

    validated_tasks: list[dict] = []
    conflicts: list[dict] = []

    for task in normalized:
        if not isinstance(task, dict):
            continue
        enriched = dict(task)
        enriched["missing_fields"] = _missing_fields(task)
        validated_tasks.append(enriched)

        title = str(task.get("title") or "")
        if not title:
            continue
        similar_candidates = [
            candidate
            for candidate in existing_tasks
            if isinstance(candidate, dict)
            and title_similarity(title, str(candidate.get("title") or "")) >= TITLE_SIMILARITY_THRESHOLD
        ]
        try:
            conflicts.extend(_build_conflicts_for_task(enriched, similar_candidates))
        except Exception as exc:
            errors.append(f"validate_tasks conflict check failed: {exc}")

    return {"validated_tasks": validated_tasks, "conflicts": conflicts, "errors": errors}
