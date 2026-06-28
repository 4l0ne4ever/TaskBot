import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete as _delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.conflict import Conflict
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskResponse,
    TaskSourceResponse,
    TaskUpdate,
    TeamMemberStats,
    TeamView,
)

_MAX_EXCERPT_CHARS = 600
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_WS_RE = re.compile(r"[ \t]{2,}")
_CRLF_RE = re.compile(r"\r\n?")


# Auto-priority thresholds — kept in lock-step with
# ``agent/app/services/save_tasks_service._derive_priority_from_deadline``
# so a task's urgency colour stays consistent whether the pipeline auto-
# confirmed it or the user clicked Confirm. ≤2 days = high (tomorrow's
# work), 3-7 = medium (this week), >7 = low (later).
_PRIORITY_HIGH_DAYS = 2
_PRIORITY_MEDIUM_DAYS = 7


def _priority_from_deadline(deadline: date) -> str:
    delta_days = (deadline - datetime.now(timezone.utc).date()).days
    if delta_days <= _PRIORITY_HIGH_DAYS:
        return "high"
    if delta_days <= _PRIORITY_MEDIUM_DAYS:
        return "medium"
    return "low"


def _clean_excerpt(raw: str | None) -> str | None:
    if not raw:
        return None
    text = _HTML_TAG_RE.sub(" ", raw)
    text = _CRLF_RE.sub("\n", text)
    text = _MULTI_WS_RE.sub(" ", text).strip()
    if len(text) > _MAX_EXCERPT_CHARS:
        text = text[:_MAX_EXCERPT_CHARS].rstrip() + "…"
    return text or None

router = APIRouter()


async def _source_type_by_doc_id(db: AsyncSession, doc_ids: list[UUID]) -> dict[UUID, str]:
    if not doc_ids:
        return {}
    r = await db.execute(
        select(SourceDocument.id, SourceDocument.source_type).where(SourceDocument.id.in_(doc_ids))
    )
    return {row[0]: row[1] for row in r.all()}


def _derive_missing_fields(task: Task) -> list[str]:
    """Round 14 (2026-05-31): the pipeline writes ``missing_fields`` once at
    extract time and the agent's update-in-place path refreshes it, but
    historical rows can carry a stale array — e.g. a task created without a
    deadline, then PATCHed with one before the Round-14 PATCH-time recompute
    landed. Deriving on read from the actual ``deadline`` / ``assignee``
    column values makes the chip and the filter agree with what the user
    sees in the row, regardless of how the row got into its current state.

    Mirrors ``agent/app/pipeline/nodes/validate_tasks._missing_fields`` so
    backend and pipeline use the same definition.
    """
    missing: list[str] = []
    if task.deadline is None:
        missing.append("deadline")
    if not task.assignee:
        missing.append("assignee")
    return missing


def _task_response(task: Task, source_type: str | None) -> TaskResponse:
    data = TaskResponse.model_validate(task).model_dump()
    data["source_type"] = source_type
    # Override the persisted array with the freshly-derived one. The stored
    # array is kept as an audit trail of what the pipeline saw at extract
    # time; what the user sees should always match the current row state.
    data["missing_fields"] = _derive_missing_fields(task)
    if not get_settings().task_v2_read_enabled:
        data["deadline_v2"] = None
        data["uncertainty"] = None
    return TaskResponse.model_validate(data)


async def _enrich_tasks(db: AsyncSession, tasks: list[Task]) -> list[TaskResponse]:
    doc_ids = [t.source_doc_id for t in tasks if t.source_doc_id]
    mapping = await _source_type_by_doc_id(db, doc_ids)
    return [
        _task_response(
            t,
            mapping.get(t.source_doc_id) if t.source_doc_id else None,
        )
        for t in tasks
    ]


def _apply_task_list_filters(
    stmt,
    *,
    status: str | None,
    source: str | None,
    deadline_from: date | None,
    deadline_to: date | None,
    missing: str | None = None,
    priority: str | None = None,
    scope: str = "active",
):
    if status:
        stmt = stmt.where(Task.status == status)
    # ``priority="none"`` is the explicit no-priority bucket — distinct from
    # leaving the filter at "All". Both are common queries: triage view picks
    # "High", review view picks "None" to find tasks that still need a manual
    # urgency call.
    if priority == "none":
        stmt = stmt.where(Task.priority.is_(None))
    elif priority:
        stmt = stmt.where(Task.priority == priority)
    if deadline_from:
        stmt = stmt.where(Task.deadline >= deadline_from)
    if deadline_to:
        stmt = stmt.where(Task.deadline <= deadline_to)
    # Round 14 (2026-05-31, revised): filter against the live column values
    # rather than the persisted ``missing_fields`` array. The array is
    # stamped once at extract time and can go stale (e.g. a task created
    # without a deadline, then PATCHed with one — pre-Round-14 the array
    # was never refreshed). Using column predicates means the filter and
    # the chip (which is also derived on read in ``_derive_missing_fields``)
    # always agree with what the user sees in the row.
    #   - "deadline"  → rows where the deadline column is NULL
    #   - "assignee"  → rows where the assignee text is NULL or empty
    #   - "any"       → either of the above
    if missing == "deadline":
        stmt = stmt.where(Task.deadline.is_(None))
    elif missing == "assignee":
        stmt = stmt.where((Task.assignee.is_(None)) | (func.length(func.trim(Task.assignee)) == 0))
    elif missing == "any":
        stmt = stmt.where(
            (Task.deadline.is_(None))
            | (Task.assignee.is_(None))
            | (func.length(func.trim(Task.assignee)) == 0)
        )
    # 2026-06-07 (v2): completed-bucket filter via ``scope`` enum. The /tasks
    # UI toggle maps to two of the three values; /tracking uses the third.
    #
    #   scope="active"    → NOT done AND NOT past-due-confirmed (default)
    #   scope="completed" → done OR past-due-confirmed (the Show-completed view)
    #   scope="all"       → no filter (every non-archived row; used by
    #                       /tracking so the Kanban Done column stays
    #                       populated alongside Todo + In Progress)
    #
    # Two flavours of "completed":
    #   1. ``progress_state = 'done'`` — Kanban-tracked completion
    #   2. ``status = 'confirmed' AND deadline < today`` — date-anchored
    #      work whose deadline has passed (presumed delivered)
    # Overdue *pending* tasks stay in the active view — they still need
    # attention, the user hasn't acknowledged them yet.
    today = date.today()
    is_done = Task.progress_state == "done"
    is_past_due_confirmed = (
        (Task.status == "confirmed")
        & Task.deadline.is_not(None)
        & (Task.deadline < today)
    )
    if scope == "completed":
        # NULL ``progress_state`` rows are not done (definitionally —
        # Kanban never moved them), so ``=`` is correct here: NULL = 'done'
        # → NULL → row excluded, which matches the completed-view intent.
        stmt = stmt.where(is_done | is_past_due_confirmed)
    elif scope == "all":
        # No completed-bucket filter — every row from the user's task table
        # passes (other filters above still apply: status, missing, etc.).
        pass
    else:  # "active" (default)
        # NULL safety: ``progress_state`` defaults to NULL for legacy rows
        # and ``deadline`` is NULL for no-deadline tasks. A naïve
        # ``(progress_state='done') OR (status='confirmed' AND deadline<today)``
        # evaluates to NULL when both sides are NULL → ``NOT NULL`` is NULL
        # → the WHERE clause drops the row. Use ``IS DISTINCT FROM`` for the
        # done check (treats NULL as "not done") and the IS NOT NULL guard on
        # deadline so a no-deadline task survives the past-due comparison.
        not_done = Task.progress_state.is_distinct_from("done")
        not_past_due = ~is_past_due_confirmed
        # Dismissed tasks are the user saying "this isn't real work" — hiding
        # them from the active view keeps the list focused on work that still
        # needs attention. An explicit status="dismissed" filter (or the
        # Revert action on the dismissed row) is still the way back.
        not_dismissed = Task.status != "dismissed"
        stmt = stmt.where(not_done & not_past_due & not_dismissed)
    if source:
        stmt = stmt.join(SourceDocument, Task.source_doc_id == SourceDocument.id).where(
            SourceDocument.source_type == source
        )
    else:
        # Round 11 (2026-05-30): /tasks defaults to inbox-only — sent-context
        # tasks (source_type='gmail_sent') belong in /team, not the personal
        # task list. The user is the *assignor* of those, not the assignee,
        # so they would be confusing noise in /tasks. To see them explicitly,
        # callers pass ?source=gmail_sent. /team aggregation does not pass
        # through this helper, so it continues to include both.
        stmt = stmt.outerjoin(SourceDocument, Task.source_doc_id == SourceDocument.id).where(
            (SourceDocument.source_type != "gmail_sent") | (SourceDocument.source_type.is_(None))
        )
    return stmt


async def _count_filtered_tasks(db: AsyncSession, user_id: UUID, **filters) -> int:
    stmt = select(Task).where(Task.user_id == user_id)
    stmt = _apply_task_list_filters(stmt, **filters)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return int((await db.execute(count_stmt)).scalar_one() or 0)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    response: Response,
    status: str | None = Query(None, pattern=r"^(pending|confirmed|dismissed)$"),
    source: str | None = Query(None, pattern=r"^(gmail|gmail_sent|drive|upload)$"),
    missing: str | None = Query(None, pattern=r"^(deadline|assignee|any)$"),
    priority: str | None = Query(None, pattern=r"^(high|medium|low|none)$"),
    deadline_from: date | None = Query(None),
    deadline_to: date | None = Query(None),
    sort: str = Query("created_desc", pattern=r"^(deadline_asc|created_desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    scope: str = Query("active", pattern=r"^(active|completed|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskResponse]:
    filters = {
        "status": status,
        "source": source,
        "deadline_from": deadline_from,
        "deadline_to": deadline_to,
        "missing": missing,
        "priority": priority,
        "scope": scope,
    }
    total = await _count_filtered_tasks(db, current_user.id, **filters)
    response.headers["X-Total-Count"] = str(total)

    stmt = select(Task).where(Task.user_id == current_user.id)
    stmt = _apply_task_list_filters(stmt, **filters)
    if sort == "deadline_asc":
        stmt = stmt.order_by(Task.deadline.asc().nulls_last(), Task.created_at.desc())
    else:
        stmt = stmt.order_by(Task.created_at.desc())

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    return await _enrich_tasks(db, tasks)


@router.get("/team", response_model=TeamView)
async def team_view(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamView:
    """Workload + risk rollup grouped by assignee (Phase 8.2 Team View).

    Single-tenant: the "team" is the set of assignees named across this user's
    tasks. Aggregation is done in Python rather than SQL — per-user task volume
    is small (tens to low hundreds), and the in-conflict flag needs membership
    in unresolved conflicts' ``task_ids`` arrays, which is awkward in grouped
    SQL but trivial as a set lookup. Registered before ``/{task_id}`` so the
    static path isn't captured by the UUID path parameter.
    """
    task_rows = list(
        (await db.execute(select(Task).where(Task.user_id == current_user.id))).scalars().all()
    )

    # Task ids that sit in an unresolved conflict → risk flag.
    conflict_rows = list(
        (
            await db.execute(
                select(Conflict).where(
                    Conflict.user_id == current_user.id,
                    Conflict.resolved == False,  # noqa: E712
                )
            )
        ).scalars().all()
    )
    conflicted_ids: set[UUID] = set()
    for c in conflict_rows:
        if c.task_ids:
            conflicted_ids.update(c.task_ids)

    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=7)

    # Bucket key: canonical name, else raw assignee, else None (unassigned).
    buckets: dict[str | None, dict[str, int]] = {}

    def _bucket(key: str | None) -> dict[str, int]:
        return buckets.setdefault(
            key,
            {
                "open": 0,
                "pending": 0,
                "confirmed": 0,
                "overdue": 0,
                "due_this_week": 0,
                "in_conflict": 0,
                "needs_review": 0,
            },
        )

    for t in task_rows:
        raw = (t.assignee_canonical or t.assignee or "").strip()
        key = raw or None
        b = _bucket(key)
        dismissed = t.status == "dismissed"
        if not dismissed:
            b["open"] += 1
            if t.status == "pending":
                b["pending"] += 1
                if t.confirmed_by is None:
                    b["needs_review"] += 1
            elif t.status == "confirmed":
                b["confirmed"] += 1
            if t.deadline is not None:
                if t.deadline < today:
                    b["overdue"] += 1
                elif today <= t.deadline <= week_end:
                    b["due_this_week"] += 1
            if t.id in conflicted_ids:
                b["in_conflict"] += 1

    def _stats(key: str | None) -> TeamMemberStats:
        b = buckets.get(key) or _bucket(key)
        return TeamMemberStats(assignee=key, **b)

    members = [
        _stats(key)
        for key in sorted((k for k in buckets if k is not None), key=str.casefold)
    ]
    # Sort the busiest first so an overloaded member surfaces at the top.
    members.sort(key=lambda m: (m.overdue, m.in_conflict, m.open), reverse=True)
    return TeamView(members=members, unassigned=_stats(None))


@router.get("/source-by-ref", response_model=TaskSourceResponse)
async def get_source_by_ref(
    ref: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskSourceResponse:
    """Look up a source document by its pipeline source_ref string.

    Used by the conflict UI when a conflict row has no task_ids — the
    source_a_ref / source_b_ref values are matched directly against
    source_documents.source_ref. Registered before ``/{task_id}`` so the
    static path isn't captured by the UUID path parameter.
    """
    stmt = select(SourceDocument).where(
        SourceDocument.source_ref == ref,
        SourceDocument.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_NOT_FOUND", "message": "Source document not found"})
    return TaskSourceResponse(
        source_type=doc.source_type,
        source_ref=doc.source_ref,
        excerpt=_clean_excerpt(doc.raw_text),
        created_at=doc.created_at,
        received_at=doc.received_at,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})
    enriched = await _enrich_tasks(db, [task])
    return enriched[0]


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})

    changes = body.model_dump(exclude_unset=True)
    # Phase 6.6 (2026-06-03): dismiss flag is a server-side control, not a
    # Task column — pop it out before the generic setattr loop. Setting it
    # to True records "now" so re-syncs of the same task suppress further
    # recurrence suggestions (recurrence_dismissed_at IS NOT NULL guard in
    # save_tasks_service).
    dismiss_suggestion = changes.pop("dismiss_recurrence_suggestion", None)
    # Capture prior recurrence_rule for the remove-recurrence flow below.
    prior_recurrence_rule = task.recurrence_rule
    # Empty-string sentinel from the validator means "clear" — translate to
    # None for the ORM. A non-None canonicalised RRULE is the new active
    # rule; clear any pending suggestion since the user is applying it.
    if "recurrence_rule" in changes:
        new_rrule = changes["recurrence_rule"]
        changes["recurrence_rule"] = new_rrule if new_rrule else None
        if changes["recurrence_rule"] is not None:
            task.recurrence_suggested = None
    for field, value in changes.items():
        setattr(task, field, value)
    if dismiss_suggestion is True:
        task.recurrence_dismissed_at = datetime.now(timezone.utc)
        task.recurrence_suggested = None
    # Phase 6.6 remove-recurrence flow: when the user clears an active
    # recurrence_rule, the FIRST upcoming occurrence becomes the new deadline
    # of a now-single task (preserves task existence — "remove recurrence"
    # ≠ "delete task"). The old Google Calendar recurring event becomes an
    # orphan in v1 — documented as a known limitation in
    # tests/e2e/real-world-validation.md §9; cleanup via a sweeper or an
    # explicit delete-event call is v2 work.
    removed_recurrence = (
        "recurrence_rule" in changes
        and changes["recurrence_rule"] is None
        and prior_recurrence_rule is not None
    )
    if removed_recurrence and task.deadline is not None:
        from app.utils.recurrence import next_occurrence

        nxt = next_occurrence(prior_recurrence_rule, task.deadline)
        if nxt is not None:
            task.deadline = nxt
        # Force recreation as a single event on the next dispatch — without
        # this the dispatch would PATCH the existing recurring event and
        # Google would keep the RRULE.
        task.calendar_event_id = None
    if changes or dismiss_suggestion is True:
        task.updated_at = datetime.now(timezone.utc)

    # confirmed_by is controlled server-side — the client only sends status.
    if changes.get("status") == "confirmed":
        task.confirmed_by = "user"
        # Mirror the agent's auto-priority rule (save_tasks_service._derive_
        # priority_from_deadline): when a user manually confirms a task that
        # has a deadline but no priority yet, infer urgency from the deadline
        # so /calendar colour-codes it without forcing a second click. We do
        # NOT override an existing priority — that was either LLM-extracted
        # from message content (e.g. "URGENT") or set deliberately by the user.
        if task.priority is None and task.deadline is not None:
            task.priority = _priority_from_deadline(task.deadline)
    elif changes.get("status") == "pending":
        task.confirmed_by = None  # intentional revert clears badge signal

    # Round 14 (2026-05-31): keep the persisted ``missing_fields`` array in
    # sync with the current row state whenever the user edits a flaggable
    # field. Read APIs derive this fresh via ``_derive_missing_fields``, so
    # the chip is always correct regardless — but persisting on write means
    # downstream consumers that read the column directly (daily digest,
    # weekly brief) also see fresh values without each having to re-derive.
    if any(k in changes for k in ("deadline", "assignee")):
        task.missing_fields = _derive_missing_fields(task)

    # When confirming a task that has a deadline, enqueue a calendar event
    # creation/update job so the event appears without requiring a full sync.
    # Phase 6.6: also enqueue when recurrence_rule changed on an already-
    # confirmed task — dispatch propagates the new RRULE (or clears it as a
    # single event when the remove-recurrence flow ran above).
    # 2026-06-28: deadline / deadline_time change on a confirmed task also
    # triggers dispatch — without this, the user moves a deadline in the UI
    # but the Google Calendar event stays anchored to the old date until
    # the next manual confirm cycle. The web /calendar view picks up the
    # change immediately (it reads ``task.deadline`` directly), so the gap
    # only shows in Google Calendar — easy to miss, hence the silent drift.
    recurrence_changed = (
        "recurrence_rule" in changes and task.status == "confirmed" and task.deadline is not None
    )
    deadline_changed_on_confirmed = (
        any(k in changes for k in ("deadline", "deadline_time"))
        and task.status == "confirmed"
        and task.deadline is not None
    )
    need_calendar = (
        changes.get("status") == "confirmed" and task.deadline is not None
    ) or recurrence_changed or deadline_changed_on_confirmed
    access_token: str | None = None
    if need_calendar:
        from app.api.conflicts import _build_calendar_resync_payload
        access_token, _ = await _build_calendar_resync_payload(current_user)

    enriched = await _enrich_tasks(db, [task])

    # Commit before enqueue so the agent reads the confirmed task, not stale state.
    await db.commit()

    if access_token:
        settings = get_settings()
        redis_client = await get_redis()
        await redis_client.rpush(
            settings.pipeline_queue_name,
            json.dumps(
                {
                    "source_type": "calendar_resync",
                    "user_id": str(current_user.id),
                    "access_token": access_token,
                    "task_id": str(task.id),
                    "triggered_by": "task_confirm",
                }
            ),
        )

    return enriched[0]


@router.delete("")
async def delete_tasks_bulk(
    status: str | None = Query(None, pattern=r"^(pending|confirmed|dismissed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    stmt = _delete(Task).where(Task.user_id == current_user.id)
    if status:
        stmt = stmt.where(Task.status == status)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount}


@router.get("/{task_id}/source", response_model=TaskSourceResponse)
async def get_task_source(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskSourceResponse:
    task_stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    task_result = await db.execute(task_stmt)
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})
    if not task.source_doc_id:
        raise HTTPException(status_code=404, detail={"code": "NO_SOURCE", "message": "Task has no source document"})

    doc_stmt = select(SourceDocument).where(
        SourceDocument.id == task.source_doc_id,
        SourceDocument.user_id == current_user.id,
    )
    doc_result = await db.execute(doc_stmt)
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_NOT_FOUND", "message": "Source document not found"})

    return TaskSourceResponse(
        source_type=doc.source_type,
        source_ref=doc.source_ref,
        excerpt=_clean_excerpt(doc.raw_text),
        created_at=doc.created_at,
        received_at=doc.received_at,
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task not found"})

    calendar_event_id = task.calendar_event_id
    await db.delete(task)
    return {"deleted": str(task_id), "calendar_event_id": calendar_event_id or ""}
