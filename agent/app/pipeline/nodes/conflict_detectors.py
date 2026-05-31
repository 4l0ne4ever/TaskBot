"""Conflict-detection helpers extracted from ``validate_tasks``.

Three scopes share these primitives:
- ``intra_batch`` (Phase 2.1 original): pairwise diff within one extraction run
- ``thread_update`` (Phase 2.1 + A'): same, but the source carries an explicit
  marker (Update:/Cập nhật:/...) that promotes the scope so the UI can show a
  timeline instead of "two extracted versions"
- ``inter_doc`` (Phase A'): cross-document but same source_type
- ``multi_source`` (Phase 2.2): cross-platform (e.g. Gmail ↔ Drive) — uses
  ``_detect_multi_source_conflicts`` which is structural-only (title + entity
  overlap) and skips the LLM call

The ``validate_tasks`` node orchestrates the order: per-task inter-doc loop →
intra-batch sweep → multi-source sweep, accumulating into one ``conflicts``
list with scope tags that the UI sorts on.
"""

from __future__ import annotations

import json
import re

from app.pipeline.llm import call_llm, llm_call_context
from app.pipeline.prompts import CONFLICT_USER_V1
from app.services.task_dedupe import title_similarity


def parse_conflict_response(raw: str) -> dict:
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


def classify_conflict(task_a: dict, task_b: dict) -> dict:
    """Run a single LLM pairwise conflict classification.

    Isolated so both the inter-document loop and the intra-batch pairwise pass
    share one code path, one prompt (``CONFLICT_USER_V1``) and one parser —
    the two loops are different selection policies over the same primitive.
    """
    with llm_call_context(node_name="validate_tasks", call_purpose="conflict_check"):
        raw = call_llm(
            CONFLICT_USER_V1.format(
                task_a_json=json.dumps(task_a, ensure_ascii=True),
                task_b_json=json.dumps(task_b, ensure_ascii=True),
            ),
            temperature=0.0,
        )
    return parse_conflict_response(raw)


def task_ref(task: dict, fallback_index: int) -> str:
    """Stable, human-readable reference for an intra-batch task.

    Uses the LLM-provided ``source_ref`` when present (which the extractor
    already emits for per-email segments of a thread) and otherwise falls back
    to the task's position in the batch. Keeping the shape stable lets conflict
    records cross-reference the tasks they point at without DB ids.
    """
    ref = task.get("source_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    return f"batch-{fallback_index}"


# ── Phase 2.1: thread-update marker detection ──────────────────────────────────
#
# A small, language-agnostic set of *structural* markers that signal "this
# email or section supersedes the earlier one for the same deliverable".
# Deliberately minimal — the anti-pattern from `taskbot-prompts` is to grow
# this list into a closed-set keyword dictionary. Each pattern targets a
# canonical announcement form (an "Update:" / "Cập nhật:" prefix, a
# reassignment verb, a "now-due / now-handled" predicate). If a future
# language carries a marker not in this list, the pair still gets detected
# as a conflict — the marker only promotes ``scope`` from "intra_batch" to
# "thread_update" so downstream UI can surface the timeline.

_THREAD_UPDATE_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Explicit "Update:" / "Updated:" / "Revised:" / "Cập nhật:" / "Đã đổi:"
    # — colon-suffixed announcement form.
    re.compile(
        r"\b(?:update|updated|revised|cập\s+nhật|đã\s+đổi|đổi\s+lại)\s*:",
        re.IGNORECASE,
    ),
    # "Revised" / "Sửa đổi" / "Sửa lại" — adjective / verb without colon.
    re.compile(r"\b(?:revised|sửa\s+(?:lại|đổi))\b", re.IGNORECASE),
    # "Now due / assigned / handled by" — predicate form.
    re.compile(r"\bnow\s+(?:due|assigned|handled)\b", re.IGNORECASE),
    # Reassignment verbs.
    re.compile(r"\breassign(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bthay\s+(?:vì|cho)\b", re.IGNORECASE),
)


def has_thread_update_marker(source_text: str | None) -> bool:
    """Return True when ``source_text`` carries any thread-update marker.

    Pure function: same input always yields the same answer. Callers use this
    to decide between ``scope="intra_batch"`` (no thread structure detected)
    and ``scope="thread_update"`` (the source explicitly signals a later
    revision).
    """
    if not source_text or not isinstance(source_text, str):
        return False
    return any(p.search(source_text) for p in _THREAD_UPDATE_MARKER_PATTERNS)


def build_conflicts_for_task(
    task: dict,
    candidates: list[dict],
    max_checks: int,
    *,
    source_text: str | None = None,
) -> list[dict]:
    # Phase A' scope: a thread-update marker in the new task's source text
    # promotes the cross-document conflict from plain ``inter_doc`` to
    # ``thread_update`` — matches the real user journey where a follow-up
    # email ("Update:", "Đã đổi:") arrives after the original task was
    # already persisted. Marker detection reuses has_thread_update_marker so
    # the intra-batch and inter-doc paths stay consistent.
    scope = "thread_update" if has_thread_update_marker(source_text) else "inter_doc"
    conflicts: list[dict] = []
    checks = 0
    for existing in candidates:
        if checks >= max_checks:
            break
        checks += 1
        parsed = classify_conflict(task, existing)
        if parsed["conflict_type"] == "no_conflict":
            continue
        conflicts.append(
            {
                "conflict_type": parsed["conflict_type"],
                "description": parsed["description"],
                "source_a_ref": task.get("source_ref"),
                "source_b_ref": existing.get("source_ref") or existing.get("id"),
                "task_title": task.get("title"),
                "scope": scope,
            }
        )
    return conflicts


def detect_intra_batch_conflicts(
    candidate_tasks: list[tuple[int, dict]],
    policy,
    *,
    budget: int,
    source_text: str | None = None,
) -> tuple[list[dict], list[tuple[int, str]]]:
    """Pairwise conflict detection across tasks emitted in the same run.

    Motivation (ac-157 family): a single email thread or document can produce
    two extracted tasks that refer to the same deliverable but disagree on
    assignee or deadline (e.g. "Đã đổi: Lê thay Hải"). The inter-document
    loop only compares the new batch against tasks already persisted in the
    DB, so a fresh reassignment inside one document was invisible.

    Resolution follows **last-writer-wins semantics** — the same rule CRDT
    LWW registers and event-sourced replay use: when two events claim the
    same resource, the later event supersedes the earlier one and the earlier
    is retained as an audit record. Here "later" is the task's position in
    the extraction order, which mirrors source-text order. We do not hard-
    code any reassignment keyword list; the LLM conflict prompt
    (``CONFLICT_USER_V1``) is the general classifier and title_similarity
    (same threshold as inter-doc) is the scoping filter.

    Scope tagging (Phase 2.1):
        ``scope="thread_update"`` when ``source_text`` carries a structural
        thread-update marker (see ``has_thread_update_marker``), otherwise
        ``scope="intra_batch"``. The promotion is purely informational — UI
        and downstream graph-traversal code can surface the thread timeline
        explicitly. Resolution semantics (last-writer-wins) are unchanged.

    Returns
    -------
    (conflicts, supersedes)
        ``conflicts`` are conflict records to append to the node output.
        ``supersedes`` is a list of ``(earlier_index, later_ref)`` tuples so
        the caller can stamp ``superseded_by`` onto the earlier task without
        this helper needing to mutate state itself.
    """
    conflicts: list[dict] = []
    supersedes: list[tuple[int, str]] = []
    checks_left = max(int(budget), 0)
    if checks_left <= 0 or len(candidate_tasks) < 2:
        return conflicts, supersedes

    threshold = policy.conflict_title_similarity_threshold
    scope = "thread_update" if has_thread_update_marker(source_text) else "intra_batch"
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
            parsed = classify_conflict(task_a, task_b)
            if parsed["conflict_type"] == "no_conflict":
                continue
            ref_a = task_ref(task_a, idx_a)
            ref_b = task_ref(task_b, idx_b)
            conflicts.append(
                {
                    "conflict_type": parsed["conflict_type"],
                    "description": parsed["description"],
                    "source_a_ref": ref_a,
                    "source_b_ref": ref_b,
                    "task_title": task_b.get("title") or title_b,
                    "scope": scope,
                }
            )
            supersedes.append((idx_a, ref_b))
            used.add(i)
            break
    return conflicts, supersedes


# ── Phase 2.2: multi-source conflict detection ────────────────────────────────
#
# "Multi-source" means *the same deliverable shows up across two different
# platforms* — e.g., a Gmail thread asks for a report, then a Drive doc
# repeats the same ask. The cross-platform aspect is what makes this scope
# distinct from intra-batch / inter-doc-same-type conflict detection.
#
# Filter pipeline (all must hold):
#   (a) title_similarity ≥ policy.multi_source_title_similarity_threshold
#   (b) different ``source_doc_id`` AND different ``source_type``
#   (c) entity-overlap rule (hybrid, see ``entity_overlap_compatible``):
#       - if BOTH sides have a non-empty person-entity set, require ≥1 overlap
#       - if either side's set is empty, the entity check is skipped — we do
#         not penalise a task because the LLM couldn't extract an assignee
#
# Resolution is intentionally informational at this layer: we emit a conflict
# event so downstream UI / digest features can surface it. We do not call the
# LLM here — title similarity + entity overlap is a high-precision structural
# signal, and an extra LLM round-trip per cross-source candidate pair would
# be expensive and have non-trivial latency.


def entity_overlap_compatible(
    new_entities: set[str], candidate_entities: set[str]
) -> bool:
    """Hybrid overlap check.

    - If either side has an empty set → True (fallback: trust title + cross-
      source filters; don't penalise tasks with no extracted assignee).
    - Otherwise → True iff at least one canonical appears in both sets.
    """
    if not new_entities or not candidate_entities:
        return True
    return bool(new_entities & candidate_entities)


def new_task_entity_set(task: dict) -> set[str]:
    """At validate-time the entity-extractor hasn't yet emitted relationships
    for the new task, so its 'entity set' is just whatever the normalize step
    produced for ``assignee_canonical`` (the only signal we have)."""
    canonical = task.get("assignee_canonical")
    if isinstance(canonical, str) and canonical.strip():
        return {canonical.strip()}
    return set()


def detect_multi_source_conflicts(
    new_tasks: list[tuple[int, dict]],
    candidates: list[dict],
    policy,
    *,
    new_source_doc_id: str | None,
    new_source_type: str | None,
) -> list[dict]:
    """Pure-function cross-source detector. Takes the new batch's validated
    tasks + a pre-loaded list of cross-source candidates (from
    ``cross_source_candidates_loader``) and returns conflict records.

    The pure-function shape lets us unit-test the matching logic without a
    database — the loader is tested separately.
    """
    conflicts: list[dict] = []
    if not new_tasks or not candidates:
        return conflicts

    threshold = policy.multi_source_title_similarity_threshold

    for idx_new, new_task in new_tasks:
        title_new = str(new_task.get("title") or "").strip()
        if not title_new:
            continue
        new_entities = new_task_entity_set(new_task)
        for cand in candidates:
            title_cand = str(cand.get("title") or "").strip()
            if not title_cand:
                continue
            # (b) different source_doc_id AND different source_type
            cand_doc = cand.get("source_doc_id")
            cand_type = cand.get("source_type")
            if not cand_doc or not cand_type:
                continue
            if new_source_doc_id and cand_doc == new_source_doc_id:
                continue
            if new_source_type and cand_type == new_source_type:
                continue
            # (a) title similarity
            if title_similarity(title_new, title_cand) < threshold:
                continue
            # (c) entity overlap (hybrid)
            cand_entities = cand.get("entity_canonicals") or set()
            if not isinstance(cand_entities, (set, frozenset)):
                cand_entities = set(cand_entities)
            if not entity_overlap_compatible(new_entities, cand_entities):
                continue
            new_ref = task_ref(new_task, idx_new)
            conflicts.append(
                {
                    "conflict_type": "multi_source",
                    "description": (
                        f"Same deliverable observed across {cand_type} (existing) "
                        f"and {new_source_type or 'current'} (new)"
                    ),
                    "source_a_ref": new_ref,
                    # Store the existing source_doc_id as the b-ref so the
                    # downstream save_tasks_service persists the linkage
                    # without needing a new column.
                    "source_b_ref": cand_doc,
                    "task_title": new_task.get("title") or title_new,
                    "scope": "multi_source",
                }
            )
    return conflicts
