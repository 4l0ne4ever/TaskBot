"""Entity graph extractor — derive person entities and assigned_to /
mentioned_in relationships from saved tasks.

Runs as a separate post-commit step after ``save_tasks_service.async_save_tasks``
(best-effort: failures log warnings but do not roll back tasks). Idempotent
per task — re-running for the same task replaces that task's relationships
without affecting other tasks' relationships.

Scope (Phase 1.2):
  - Person entities only (no topic / project — those need LLM-grade extraction
    and noisy heuristics are deferred to Phase 2+).
  - ``assigned_to`` edges (person → task) from ``task.assignee_canonical``.
  - ``mentioned_in`` edges (person → task) from word-boundary scan of the
    per-user *known canonical pool* against ``task.title + description +
    evidence_quote``. The pool comes from the entities table itself — only
    persons who are an assignee of some task can be picked up as "mentioned"
    elsewhere. This deliberately avoids inventing entities for arbitrary
    strings.

Out of scope (Phase 2+, documented for future expansion):
  - 'topic' / 'project' entity types (LLM-grade problem).
  - 'collaborates_with' edges (co-occurrence within a source_doc).
  - 'depends_on' / 'blocks' / 'related_to' relationship types.
  - Free-form NER for mentioned names beyond the canonical pool.

Design notes:
  - The detector is **diacritic-sensitive** to match ``assignee_resolver`` —
    "Hương" in the pool will not match "Huong" in text. This is consistent
    with how the resolver decides canonicality and avoids silent over-matching.
  - Relationship upsert is *replace-per-task*: for each task we delete the
    edges this module owns (``assigned_to``, ``mentioned_in``) before inserting
    fresh ones, so re-running the pipeline doesn't accumulate duplicates and
    third-party edges (future Phase-2 emitters) stay untouched.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entity, Relationship

logger = logging.getLogger(__name__)


# Relationship types this module owns. The refresh step deletes only edges
# with these types so future emitters (Phase 2: depends_on / blocks /
# related_to / collaborates_with) can coexist without being clobbered.
_OWNED_RELATIONSHIP_TYPES: tuple[str, ...] = ("assigned_to", "mentioned_in")

PERSON_ENTITY_TYPE = "person"


# ── Pure helper: pool-driven mention detection ─────────────────────────────────

def find_mentioned_canonicals(
    text: str | None,
    pool: Iterable[str],
    *,
    exclude: str | None = None,
) -> list[str]:
    """Return the subset of ``pool`` whose canonical names appear as
    word-boundary matches in ``text``. Diacritic-sensitive.

    ``exclude``: a canonical to skip (typically the task's assignee, since it
    is already represented by the ``assigned_to`` edge). Matched
    case-insensitively against ``pool`` entries.

    The returned list preserves the order in which canonicals were yielded by
    ``pool`` and contains no duplicates.
    """
    if not text or not isinstance(text, str):
        return []
    excl = (exclude or "").strip().lower() if isinstance(exclude, str) else ""
    out: list[str] = []
    seen: set[str] = set()
    for canonical in pool:
        if not isinstance(canonical, str):
            continue
        cleaned = canonical.strip()
        if not cleaned:
            continue
        if cleaned.lower() == excl:
            continue
        if cleaned in seen:
            continue
        # Word-boundary regex; Python's ``\b`` is Unicode-aware for str
        # patterns, so Vietnamese diacritic letters behave as word chars.
        pattern = rf"\b{re.escape(cleaned)}\b"
        if re.search(pattern, text, flags=re.UNICODE):
            out.append(cleaned)
            seen.add(cleaned)
    return out


# ── DB ops: upsert + refresh ───────────────────────────────────────────────────

async def upsert_person_entity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    canonical: str,
    raw_alias: str | None = None,
) -> uuid.UUID:
    """Idempotently upsert a person entity keyed on
    ``(user_id, 'person', canonical)``. Returns the entity id.

    If the entity already exists and ``raw_alias`` differs from ``canonical``
    and isn't already present in ``aliases``, it is appended in-place.
    """
    canonical_clean = canonical.strip() if isinstance(canonical, str) else ""
    if not canonical_clean:
        raise ValueError("canonical must be a non-empty string")

    existing_stmt = select(Entity).where(
        Entity.user_id == user_id,
        Entity.entity_type == PERSON_ENTITY_TYPE,
        Entity.canonical_name == canonical_clean,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()

    alias_clean = raw_alias.strip() if isinstance(raw_alias, str) and raw_alias.strip() else None

    if existing is not None:
        if alias_clean and alias_clean != canonical_clean:
            current_aliases = list(existing.aliases or [])
            if alias_clean not in current_aliases:
                current_aliases.append(alias_clean)
                existing.aliases = current_aliases
        return existing.id

    initial_aliases: list[str] = []
    if alias_clean and alias_clean != canonical_clean:
        initial_aliases.append(alias_clean)

    entity = Entity(
        id=uuid.uuid4(),
        user_id=user_id,
        entity_type=PERSON_ENTITY_TYPE,
        canonical_name=canonical_clean,
        aliases=initial_aliases,
    )
    session.add(entity)
    await session.flush()
    return entity.id


async def refresh_task_relationships(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    assignee_entity_id: uuid.UUID | None,
    mentioned_entity_ids: Iterable[uuid.UUID],
    source_doc_id: uuid.UUID | None,
) -> int:
    """Replace this task's ``assigned_to`` + ``mentioned_in`` edges.

    Step 1: delete edges in our scope for ``task_id``.
    Step 2: insert a single ``assigned_to`` edge (if assignee provided) and
            one ``mentioned_in`` edge per mentioned entity. Mentions that
            coincide with the assignee or with another mention are skipped.

    Returns the number of edges newly inserted (for telemetry / tests).
    """
    del_stmt = delete(Relationship).where(
        Relationship.user_id == user_id,
        Relationship.to_task_id == task_id,
        Relationship.relationship_type.in_(_OWNED_RELATIONSHIP_TYPES),
    )
    await session.execute(del_stmt)

    inserted = 0
    seen: set[uuid.UUID] = set()

    if assignee_entity_id is not None:
        session.add(
            Relationship(
                id=uuid.uuid4(),
                user_id=user_id,
                from_entity_id=assignee_entity_id,
                to_task_id=task_id,
                relationship_type="assigned_to",
                source_doc_id=source_doc_id,
            )
        )
        seen.add(assignee_entity_id)
        inserted += 1

    for ent_id in mentioned_entity_ids:
        if ent_id is None or ent_id in seen:
            continue
        seen.add(ent_id)
        session.add(
            Relationship(
                id=uuid.uuid4(),
                user_id=user_id,
                from_entity_id=ent_id,
                to_task_id=task_id,
                relationship_type="mentioned_in",
                source_doc_id=source_doc_id,
            )
        )
        inserted += 1

    await session.flush()
    return inserted


# ── Orchestrator ───────────────────────────────────────────────────────────────

def _gather_task_text(task: dict) -> str:
    """Concatenate fields a person name could appear in. None-safe."""
    parts = [task.get("title"), task.get("description"), task.get("evidence_quote")]
    return " ".join(p for p in parts if isinstance(p, str) and p.strip())


async def update_entity_graph_for_tasks(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tasks: list[dict],
    source_doc_id: uuid.UUID | None,
) -> dict:
    """Two-pass entity-graph update for a batch of saved tasks.

      Pass 1 — upsert a person entity for every task's ``assignee_canonical``.
      Pass 2 — snapshot the user's now-complete person pool, scan each task's
               text for other pool members, and refresh edges per task.

    The function returns a small summary dict (``{entities_upserted,
    relationships_emitted}``) intended for telemetry. Idempotent: running it
    twice on the same input produces the same final graph state.

    The caller is responsible for managing the transaction (this function only
    issues ORM operations against ``session``).
    """
    summary = {"entities_upserted": 0, "relationships_emitted": 0}
    if not tasks:
        return summary

    # ── Pass 1: upsert assignees ───────────────────────────────────────────
    assignee_entity_by_task_id: dict[uuid.UUID, uuid.UUID | None] = {}
    for t in tasks:
        tid_raw = t.get("id")
        if tid_raw is None:
            continue
        task_uuid = tid_raw if isinstance(tid_raw, uuid.UUID) else uuid.UUID(str(tid_raw))

        canonical = t.get("assignee_canonical")
        raw = t.get("assignee")
        if isinstance(canonical, str) and canonical.strip():
            eid = await upsert_person_entity(
                session,
                user_id=user_id,
                canonical=canonical,
                raw_alias=raw if isinstance(raw, str) else None,
            )
            assignee_entity_by_task_id[task_uuid] = eid
            summary["entities_upserted"] += 1
        else:
            assignee_entity_by_task_id[task_uuid] = None

    # ── Pass 2: scan text for mentions, refresh relationships ──────────────
    pool_stmt = select(Entity.id, Entity.canonical_name).where(
        Entity.user_id == user_id,
        Entity.entity_type == PERSON_ENTITY_TYPE,
    )
    pool_rows = (await session.execute(pool_stmt)).all()
    canonical_to_id: dict[str, uuid.UUID] = {
        row.canonical_name: row.id for row in pool_rows if row.canonical_name
    }
    pool_canonicals = list(canonical_to_id.keys())

    for t in tasks:
        tid_raw = t.get("id")
        if tid_raw is None:
            continue
        task_uuid = tid_raw if isinstance(tid_raw, uuid.UUID) else uuid.UUID(str(tid_raw))

        assignee_eid = assignee_entity_by_task_id.get(task_uuid)
        assignee_canonical = t.get("assignee_canonical") if isinstance(t.get("assignee_canonical"), str) else None

        mentioned_names = find_mentioned_canonicals(
            _gather_task_text(t),
            pool_canonicals,
            exclude=assignee_canonical,
        )
        mentioned_ids = [canonical_to_id[m] for m in mentioned_names if m in canonical_to_id]

        added = await refresh_task_relationships(
            session,
            user_id=user_id,
            task_id=task_uuid,
            assignee_entity_id=assignee_eid,
            mentioned_entity_ids=mentioned_ids,
            source_doc_id=source_doc_id,
        )
        summary["relationships_emitted"] += added

    return summary
