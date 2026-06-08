import re
import unicodedata
import uuid

from app.pipeline.calibration import Calibrator, get_runtime_calibrator
from app.pipeline.nodes.conflict_detectors import (
    build_conflicts_for_task,
    detect_intra_batch_conflicts,
    detect_multi_source_conflicts,
    entity_overlap_compatible,
    has_thread_update_marker,
)
from app.pipeline.policy import get_pipeline_policy
from app.pipeline.state import PipelineState
from app.services.cross_source_candidates_loader import load_cross_source_candidates_sync
from app.services.existing_tasks_loader import load_existing_tasks_for_validate_sync
from app.services.observability import record_pipeline_run_trace
from app.services.task_dedupe import title_similarity

# Back-compat re-exports for unit tests that previously reached into this
# module for the internal helpers. The conflict detectors now live in
# ``conflict_detectors`` but tests still import via the old paths.
_has_thread_update_marker = has_thread_update_marker
_detect_multi_source_conflicts = detect_multi_source_conflicts
_detect_intra_batch_conflicts = detect_intra_batch_conflicts
_entity_overlap_compatible = entity_overlap_compatible

# Scope specificity for cross-detector dedup. Higher number wins when two
# scopes fire on the same (new task, existing task) pair. ``multi_source``
# is the most generic ("same deliverable across platforms") and loses to
# any scope that encodes an actionable specific (deadline conflict,
# reassignment, merge action). Mirror this order if you add a new scope.
_SCOPE_SPECIFICITY: dict[str, int] = {
    "thread_update": 3,
    "inter_doc": 2,
    "intra_batch": 1,
    "multi_source": 0,
}


def _pair_signature(c: dict) -> tuple[str, str] | None:
    """Identify the (new task, existing task) pair a conflict refers to.

    Returns ``None`` when the pair cannot be derived (then the conflict is
    treated as un-dedupable and left alone). Uses ``task_title`` to identify
    the A side (the new task; same title across detectors for the same
    emitter) and the existing task uuid for the B side. The B side is read
    from ``task_id_b`` (multi_source detector) first, then ``source_b_ref``
    parsed as UUID (thread_update / inter_doc detectors put the existing
    task's uuid there).
    """
    title = (c.get("task_title") or "").strip().lower()
    if not title:
        return None
    tid_b_raw = c.get("task_id_b")
    if not tid_b_raw:
        tid_b_raw = c.get("source_b_ref")
    if not tid_b_raw:
        return None
    try:
        tid_b = str(uuid.UUID(str(tid_b_raw)))
    except (ValueError, TypeError):
        # source_b_ref might be a free-form ref (e.g. ``batch-0`` from
        # intra_batch detector). Use the string as-is — still unique enough
        # to dedup within a single validate_tasks invocation.
        tid_b = str(tid_b_raw)
    return (title, tid_b)


def _dedup_conflicts_by_pair(conflicts: list[dict]) -> list[dict]:
    """Collapse conflicts that target the same task pair, keeping the most
    specific scope. Conflicts without a derivable pair signature pass through
    unchanged."""
    if not conflicts:
        return conflicts
    seen: dict[tuple[str, str], int] = {}
    keep: list[dict] = []
    for c in conflicts:
        sig = _pair_signature(c)
        if sig is None:
            keep.append(c)
            continue
        spec_new = _SCOPE_SPECIFICITY.get(c.get("scope") or "", 0)
        if sig in seen:
            existing_idx = seen[sig]
            spec_old = _SCOPE_SPECIFICITY.get(keep[existing_idx].get("scope") or "", 0)
            if spec_new > spec_old:
                keep[existing_idx] = c
            continue
        seen[sig] = len(keep)
        keep.append(c)
    return keep


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


def _get_existing_tasks(state: PipelineState) -> list[dict]:
    if "existing_tasks" in state:
        raw = state.get("existing_tasks")
        return raw if isinstance(raw, list) else []
    return load_existing_tasks_for_validate_sync(state)


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
                build_conflicts_for_task(
                    enriched,
                    similar_candidates,
                    policy.max_conflict_checks_per_task,
                    source_text=state.get("cleaned_text") if isinstance(state.get("cleaned_text"), str) else None,
                )
            )
        except Exception as exc:
            errors.append(f"validate_tasks conflict check failed: {exc}")

    try:
        intra_candidates = [
            (idx, vt) for idx, vt in enumerate(validated_tasks) if not vt.get("abstained")
        ]
        intra_conflicts, supersedes = detect_intra_batch_conflicts(
            intra_candidates,
            policy,
            budget=policy.max_conflict_checks_per_task,
            source_text=state.get("cleaned_text") if isinstance(state.get("cleaned_text"), str) else None,
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

    # ── Phase 2.2: multi-source (cross-platform) conflict detection ──────────
    # Best-effort like the other conflict passes: a loader failure (e.g. DB
    # unreachable) is logged into ``errors`` but never blocks task validation.
    try:
        ms_candidates = load_cross_source_candidates_sync(
            state,
            lookback_days=policy.multi_source_conflict_lookback_days,
        )
        if ms_candidates:
            ms_new_tasks = [
                (idx, vt) for idx, vt in enumerate(validated_tasks) if not vt.get("abstained")
            ]
            new_source_doc_id = (
                state.get("source_doc_id") if isinstance(state.get("source_doc_id"), str) else None
            )
            new_source_type = (
                state.get("source_type") if isinstance(state.get("source_type"), str) else None
            )
            ms_conflicts = detect_multi_source_conflicts(
                ms_new_tasks,
                ms_candidates,
                policy,
                new_source_doc_id=new_source_doc_id,
                new_source_type=new_source_type,
            )
            conflicts.extend(ms_conflicts)
    except Exception as exc:
        errors.append(f"validate_tasks multi-source conflict check failed: {exc}")

    # ── Cross-detector dedup ────────────────────────────────────────────────
    # The three passes above run independently; nothing stops two of them
    # from raising on the *same* (new task, existing task) pair. The 2026-06-08
    # forensic showed an upload vs an existing gmail task firing both
    # multi_source (different source types) and thread_update (different
    # deadlines), producing two cards for one underlying conflict. Collapse
    # them: keep the more specific scope (thread_update > inter_doc >
    # intra_batch > multi_source) — multi_source is the most generic
    # "same deliverable across sources" label, the others encode actionable
    # specifics (deadline diff, reassignment, merge button).
    conflicts = _dedup_conflicts_by_pair(conflicts)

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
