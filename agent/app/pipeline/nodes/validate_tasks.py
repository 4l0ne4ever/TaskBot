import json
import re
import unicodedata

from app.pipeline.calibration import Calibrator, get_runtime_calibrator
from app.pipeline.llm import call_llm, llm_call_context
from app.pipeline.policy import get_pipeline_policy
from app.pipeline.prompts import CONFLICT_USER_V1
from app.pipeline.state import PipelineState
from app.services.existing_tasks_loader import load_existing_tasks_for_validate_sync
from app.services.observability import record_pipeline_run_trace
from app.services.task_dedupe import title_similarity


def _to_confidence(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return None


def _apply_calibration(raw: float | None, calibrator: Calibrator | None) -> float | None:
    """Remap raw verbalized confidence to the calibrated scale.

    Keeps ``None`` as ``None`` (missing confidence must not be rescued by the
    calibrator — that should stay an abstain signal) and clamps the output
    back to ``[0, 1]`` so downstream math cannot escape the unit interval if a
    bad artifact somehow slipped past the loader's validation.
    """
    if raw is None or calibrator is None:
        return raw
    mapped = calibrator.apply(raw)
    try:
        f = float(mapped)
    except (TypeError, ValueError):
        return raw
    if f != f:  # NaN
        return raw
    return max(0.0, min(1.0, f))


def _decision_band(confidence: float | None, policy) -> str:
    if confidence is None:
        return "abstain"
    if confidence < policy.confidence_abstain_threshold:
        return "abstain"
    if confidence < policy.confidence_uncertain_threshold:
        return "uncertain"
    return "accept"


def _evidence_quote_invalid(task: dict, state: PipelineState, policy) -> bool:
    if not policy.validate_evidence_in_source:
        return False
    q = task.get("evidence_quote")
    if not isinstance(q, str) or not q.strip():
        return False
    src = state.get("cleaned_text")
    if not isinstance(src, str) or not src.strip():
        return False
    return _normalize_quote_text(q) not in _normalize_quote_text(src)


def _normalize_quote_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


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


def _classify_conflict(task_a: dict, task_b: dict) -> dict:
    """Run a single LLM pairwise conflict classification.

    Isolated so both the inter-document loop and the intra-batch
    pairwise pass share one code path, one prompt (``CONFLICT_USER_V1``)
    and one parser — the two loops are different selection policies over
    the same primitive.
    """
    with llm_call_context(node_name="validate_tasks", call_purpose="conflict_check"):
        raw = call_llm(
            CONFLICT_USER_V1.format(
                task_a_json=json.dumps(task_a, ensure_ascii=True),
                task_b_json=json.dumps(task_b, ensure_ascii=True),
            ),
            temperature=0.0,
        )
    return _parse_conflict_response(raw)


def _build_conflicts_for_task(task: dict, candidates: list[dict], max_checks: int) -> list[dict]:
    conflicts: list[dict] = []
    checks = 0
    for existing in candidates:
        if checks >= max_checks:
            break
        checks += 1
        parsed = _classify_conflict(task, existing)
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


def _task_ref(task: dict, fallback_index: int) -> str:
    """Stable, human-readable reference for an intra-batch task.

    Uses the LLM-provided ``source_ref`` when present (which the extractor
    already emits for things like per-email segments of a thread) and
    otherwise falls back to the task's position in the batch. Keeping the
    shape stable lets conflict records cross-reference the tasks they
    point at without requiring DB ids.
    """
    ref = task.get("source_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    return f"batch-{fallback_index}"


def _detect_intra_batch_conflicts(
    candidate_tasks: list[tuple[int, dict]],
    policy,
    *,
    budget: int,
) -> tuple[list[dict], list[tuple[int, str]]]:
    """Pairwise conflict detection across tasks emitted in the same run.

    Motivation (ac-157 family): a single email thread or document can
    produce two extracted tasks that refer to the same deliverable but
    disagree on assignee or deadline (e.g. "Đã đổi: Lê thay Hải"). The
    inter-document loop above only compares the new batch against tasks
    already persisted in the DB, so a fresh reassignment inside one
    document was invisible.

    Resolution follows **last-writer-wins semantics** — the same rule
    CRDT LWW registers and event-sourced replay use: when two events
    claim the same resource, the later event supersedes the earlier one
    and the earlier is retained as an audit record. Here "later" is the
    task's position in the extraction order, which mirrors source-text
    order. We do not hard-code any reassignment keyword list; the LLM
    conflict prompt (``CONFLICT_USER_V1``) is the general classifier and
    title_similarity (same threshold as inter-doc) is the scoping filter.

    Returns
    -------
    (conflicts, supersedes)
        ``conflicts`` are conflict records to append to the node output.
        ``supersedes`` is a list of ``(earlier_index, later_ref)`` tuples
        so the caller can stamp ``superseded_by`` onto the earlier task
        without this helper needing to mutate state itself.
    """
    conflicts: list[dict] = []
    supersedes: list[tuple[int, str]] = []
    checks_left = max(int(budget), 0)
    if checks_left <= 0 or len(candidate_tasks) < 2:
        return conflicts, supersedes

    threshold = policy.conflict_title_similarity_threshold
    n = len(candidate_tasks)
    used: set[int] = set()
    for i in range(n):
        if checks_left <= 0:
            break
        if i in used:
            continue
        idx_a, task_a = candidate_tasks[i]
        title_a = str(task_a.get("title") or "").strip()
        if not title_a:
            continue
        for j in range(i + 1, n):
            if checks_left <= 0:
                break
            if j in used:
                continue
            idx_b, task_b = candidate_tasks[j]
            title_b = str(task_b.get("title") or "").strip()
            if not title_b:
                continue
            if title_similarity(title_a, title_b) < threshold:
                continue
            checks_left -= 1
            parsed = _classify_conflict(task_a, task_b)
            if parsed["conflict_type"] == "no_conflict":
                continue
            ref_a = _task_ref(task_a, idx_a)
            ref_b = _task_ref(task_b, idx_b)
            conflicts.append(
                {
                    "conflict_type": parsed["conflict_type"],
                    "description": parsed["description"],
                    "source_a_ref": ref_a,
                    "source_b_ref": ref_b,
                    "task_title": task_b.get("title") or title_b,
                    "scope": "intra_batch",
                }
            )
            supersedes.append((idx_a, ref_b))
            used.add(i)
            break
    return conflicts, supersedes


def validate_tasks(state: PipelineState) -> dict:
    policy = get_pipeline_policy()
    calibrator = get_runtime_calibrator()
    normalized = state.get("normalized_tasks", [])
    errors = list(state.get("errors", []))
    existing_tasks = _get_existing_tasks(state)

    validated_tasks: list[dict] = []
    conflicts: list[dict] = []
    # Q-02 instrumentation: quote coverage + invalid drops per run, exposed
    # through pipeline_run_trace so the dashboard can tell us how often the
    # LLM actually attaches an evidence quote and how often the quote fails
    # the "substring of source" contract.
    evidence_stats = {"tasks_with_quote": 0, "invalid_quote_drops": 0}
    calibration_info: dict[str, object] = {
        "applied": calibrator is not None,
        "method": calibrator.method if calibrator else None,
        "version": calibrator.version_tag() if calibrator else None,
        "remapped_count": 0,
    }

    for task in normalized:
        if not isinstance(task, dict):
            continue
        enriched = dict(task)
        raw_confidence = _to_confidence(enriched.get("confidence"))
        calibrated = _apply_calibration(raw_confidence, calibrator)
        confidence = calibrated if calibrated is not None else raw_confidence
        band = _decision_band(confidence, policy)
        enriched["confidence"] = confidence
        enriched["raw_confidence"] = raw_confidence
        enriched["decision_score"] = confidence
        enriched["decision_band"] = band
        enriched["abstained"] = band == "abstain"
        if calibrator is not None and raw_confidence is not None:
            enriched["calibration_version"] = calibrator.version_tag()
            enriched["calibration_method"] = calibrator.method
            calibration_info["remapped_count"] = int(calibration_info["remapped_count"]) + 1
        if band == "uncertain" and not isinstance(enriched.get("uncertainty"), dict):
            enriched["uncertainty"] = {
                "type": "ambiguous",
                "reason": "confidence in uncertain band",
            }
        if band == "abstain":
            enriched["uncertainty"] = {
                "type": "missing",
                "reason": "missing confidence" if confidence is None else "confidence below abstain threshold",
            }
        enriched["missing_fields"] = _missing_fields(task)
        q = task.get("evidence_quote")
        if isinstance(q, str) and q.strip():
            evidence_stats["tasks_with_quote"] += 1
        if _evidence_quote_invalid(enriched, state, policy):
            evidence_stats["invalid_quote_drops"] += 1
            enriched["decision_band"] = "abstain"
            enriched["abstained"] = True
            enriched["uncertainty"] = {
                "type": "missing",
                "reason": "evidence_quote not found in source text",
            }
        validated_tasks.append(enriched)
        if enriched["abstained"]:
            continue

        title = str(task.get("title") or "")
        if not title:
            continue
        similar_candidates = [
            candidate
            for candidate in existing_tasks
            if isinstance(candidate, dict)
            and title_similarity(title, str(candidate.get("title") or "")) >= policy.conflict_title_similarity_threshold
        ]
        try:
            conflicts.extend(
                _build_conflicts_for_task(enriched, similar_candidates, policy.max_conflict_checks_per_task)
            )
        except Exception as exc:
            errors.append(f"validate_tasks conflict check failed: {exc}")

    try:
        intra_candidates = [
            (idx, vt) for idx, vt in enumerate(validated_tasks) if not vt.get("abstained")
        ]
        intra_conflicts, supersedes = _detect_intra_batch_conflicts(
            intra_candidates,
            policy,
            budget=policy.max_conflict_checks_per_task,
        )
        conflicts.extend(intra_conflicts)
        for earlier_idx, later_ref in supersedes:
            validated_tasks[earlier_idx]["superseded_by"] = later_ref
            validated_tasks[earlier_idx]["decision_band"] = "abstain"
            validated_tasks[earlier_idx]["abstained"] = True
            existing_uncertainty = validated_tasks[earlier_idx].get("uncertainty")
            reason = f"superseded by later revision in same document ({later_ref})"
            if not isinstance(existing_uncertainty, dict):
                validated_tasks[earlier_idx]["uncertainty"] = {
                    "type": "superseded",
                    "reason": reason,
                }
            else:
                existing_uncertainty.setdefault("type", "superseded")
                existing_uncertainty.setdefault("reason", reason)
    except Exception as exc:
        errors.append(f"validate_tasks intra-batch conflict check failed: {exc}")

    from app.pipeline.llm import summarize_provenance

    provenance_summary = summarize_provenance()
    record_pipeline_run_trace(
        state,
        validated_tasks,
        policy.version,
        provenance_summary=provenance_summary,
        evidence_stats=evidence_stats,
        calibration_info=calibration_info,
    )

    return {
        "validated_tasks": validated_tasks,
        "conflicts": conflicts,
        "errors": errors,
        "llm_provenance_summary": provenance_summary,
    }
