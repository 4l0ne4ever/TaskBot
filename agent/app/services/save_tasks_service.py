import asyncio
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.conflict import Conflict
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.pipeline.state import PipelineState
from app.services.assignee_resolver import get_default_resolver
from app.services.entity_extractor import update_entity_graph_for_tasks
from app.services.task_dedupe import pick_task_to_reuse


def _parse_deadline(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _coerce_deadline_time(value: object) -> time | None:
    """Round 13: normalize_tasks emits a ``datetime.time`` (or None) in the
    ``deadline_time`` field. Pass it through to the Task row unchanged when
    present, else None. Strings "HH:MM" / "HH:MM:SS" are also accepted in
    case a caller (test, future API) hands us serialized form."""
    _time = time  # local alias keeps the body identical to its prior form
    if value is None:
        return None
    if isinstance(value, _time):
        return value
    if isinstance(value, str):
        try:
            return _time.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def async_save_tasks(state: PipelineState) -> dict:
    errors = list(state.get("errors", []))
    saved_task_ids: list[str] = []

    user_id_str = state.get("user_id")
    source_doc_id_str = state.get("source_doc_id")
    user_uuid = _parse_uuid(user_id_str if isinstance(user_id_str, str) else None)
    source_doc_uuid = _parse_uuid(source_doc_id_str if isinstance(source_doc_id_str, str) else None)

    if not user_uuid or not source_doc_uuid:
        errors.append("save_tasks: missing or invalid user_id or source_doc_id")
        return {"saved_task_ids": [], "errors": errors}

    content_hash = state.get("content_hash")
    content_hash_str = content_hash if isinstance(content_hash, str) and content_hash else None

    pipeline_run_id_str = state.get("pipeline_run_id")
    validated_tasks = [t for t in (state.get("validated_tasks") or []) if isinstance(t, dict)]
    conflicts = [c for c in (state.get("conflicts") or []) if isinstance(c, dict)]

    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                run: PipelineRun | None = None
                pipeline_run_uuid = _parse_uuid(
                    pipeline_run_id_str if isinstance(pipeline_run_id_str, str) else None,
                )

                if pipeline_run_uuid:
                    run = await session.get(PipelineRun, pipeline_run_uuid)
                    if not run or run.user_id != user_uuid:
                        errors.append("save_tasks: pipeline_run not found or user mismatch")
                        return {"saved_task_ids": [], "errors": errors}
                else:
                    run = PipelineRun(
                        id=uuid.uuid4(),
                        user_id=user_uuid,
                        source_doc_id=source_doc_uuid,
                        status="running",
                    )
                    session.add(run)
                    await session.flush()

                meta = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
                mg_raw = meta.get("dedupe_group_id")
                mg = mg_raw.strip() if isinstance(mg_raw, str) else ""

                doc = await session.get(SourceDocument, source_doc_uuid)
                if doc and mg and not (doc.dedupe_group_id or "").strip():
                    doc.dedupe_group_id = mg
                await session.flush()

                if content_hash_str:
                    dup_stmt = (
                        select(SourceDocument.id)
                        .where(
                            SourceDocument.user_id == user_uuid,
                            SourceDocument.content_hash == content_hash_str,
                            SourceDocument.id != source_doc_uuid,
                        )
                        .limit(1)
                    )
                    dup_result = await session.execute(dup_stmt)
                    if dup_result.scalar_one_or_none():
                        run.status = "completed"
                        run.tasks_extracted = 0
                        run.conflicts_found = 0
                        run.completed_at = datetime.now(UTC)
                        run.error_message = "duplicate content_hash skipped"
                        errors.append("save_tasks: duplicate content_hash for another document; skipped inserts")
                        doc_dup = await session.get(SourceDocument, source_doc_uuid)
                        if doc_dup:
                            doc_dup.processed_at = datetime.now(UTC)
                            doc_dup.pipeline_run_id = run.id
                        return {"saved_task_ids": [], "errors": errors}

                group_id = (doc.dedupe_group_id or "").strip() if doc else ""
                if not group_id and mg:
                    group_id = mg

                reuse_rows: list[Task] = []
                if group_id:
                    pool_stmt = (
                        select(Task)
                        .join(SourceDocument, Task.source_doc_id == SourceDocument.id)
                        .where(
                            Task.user_id == user_uuid,
                            SourceDocument.dedupe_group_id == group_id,
                        )
                    )
                    reuse_rows = list((await session.execute(pool_stmt)).scalars().all())

                # Titles that appear in an intra-batch conflict — auto-confirm
                # must not fire for conflicted tasks; they need human review.
                conflicting_titles: set[str] = {
                    c.get("task_title", "").strip()
                    for c in conflicts
                    if isinstance(c.get("task_title"), str)
                }

                reused_ids: set[uuid.UUID] = set()
                title_to_new_id: dict[str, uuid.UUID] = {}
                for vt in validated_tasks:
                    if bool(vt.get("abstained")):
                        continue
                    title = vt.get("title")
                    if not isinstance(title, str) or not title.strip():
                        continue
                    tkey = title.strip()
                    best: Task | None = None
                    if group_id:
                        best = pick_task_to_reuse(reuse_rows, tkey, excluded_ids=reused_ids)
                    if best is not None:
                        reused_ids.add(best.id)
                        best.previous_revision = {
                            "title": best.title,
                            "description": best.description,
                            "assignee": best.assignee,
                            "deadline": best.deadline.isoformat() if best.deadline else None,
                            "deadline_v2": best.deadline_v2,
                            "priority": best.priority,
                            "uncertainty": best.uncertainty,
                            "source_doc_id": str(best.source_doc_id) if best.source_doc_id else None,
                            "updated_at": best.updated_at.isoformat() if hasattr(best.updated_at, "isoformat") else str(best.updated_at),
                        }
                        best.title = tkey
                        best.description = vt.get("description") if isinstance(vt.get("description"), str) else None
                        best.assignee = vt.get("assignee") if isinstance(vt.get("assignee"), str) else None
                        best.assignee_canonical = vt.get("assignee_canonical") if isinstance(vt.get("assignee_canonical"), str) else None
                        best.deadline = _parse_deadline(vt.get("deadline"))
                        best.deadline_time = _coerce_deadline_time(vt.get("deadline_time"))
                        best.deadline_v2 = vt.get("deadline_v2") if isinstance(vt.get("deadline_v2"), dict) else None
                        best.priority = vt.get("priority") if isinstance(vt.get("priority"), str) else None
                        best.uncertainty = vt.get("uncertainty") if isinstance(vt.get("uncertainty"), dict) else None
                        best.missing_fields = list(vt.get("missing_fields") or [])
                        # Refresh the evidence quote from this re-extraction: a
                        # newer message in the same dedupe group may carry a
                        # better-supported quote, so keep it in sync rather than
                        # leaving the stale prior value.
                        best.evidence_quote = (
                            vt.get("evidence_quote") if isinstance(vt.get("evidence_quote"), str) else None
                        )
                        best.source_doc_id = source_doc_uuid
                        best.updated_at = datetime.now(UTC)
                        if best.status == "confirmed":
                            best.status = "pending"
                        saved_task_ids.append(str(best.id))
                        title_to_new_id[tkey] = best.id
                    else:
                        tid = uuid.uuid4()
                        task = Task(
                            id=tid,
                            user_id=user_uuid,
                            source_doc_id=source_doc_uuid,
                            title=tkey,
                            status="pending",
                            description=vt.get("description") if isinstance(vt.get("description"), str) else None,
                            assignee=vt.get("assignee") if isinstance(vt.get("assignee"), str) else None,
                            assignee_canonical=vt.get("assignee_canonical") if isinstance(vt.get("assignee_canonical"), str) else None,
                            deadline=_parse_deadline(vt.get("deadline")),
                            deadline_time=_coerce_deadline_time(vt.get("deadline_time")),
                            deadline_v2=vt.get("deadline_v2") if isinstance(vt.get("deadline_v2"), dict) else None,
                            priority=vt.get("priority") if isinstance(vt.get("priority"), str) else None,
                            uncertainty=vt.get("uncertainty") if isinstance(vt.get("uncertainty"), dict) else None,
                            missing_fields=list(vt.get("missing_fields") or []),
                            evidence_quote=vt.get("evidence_quote") if isinstance(vt.get("evidence_quote"), str) else None,
                        )
                        # Auto-confirm: high-confidence new tasks need zero clicks.
                        # Criteria: pipeline's calibrated band (uncertainty IS NULL)
                        # + not involved in an intra-batch conflict (needs human
                        # resolution) + at least one actionable field so the task
                        # is meaningful enough to calendar/assign without review.
                        if (
                            task.uncertainty is None
                            and tkey not in conflicting_titles
                            and (task.deadline is not None or task.assignee is not None)
                        ):
                            task.status = "confirmed"
                            task.confirmed_by = "system"
                        session.add(task)
                        saved_task_ids.append(str(tid))
                        title_to_new_id[tkey] = tid

                if group_id and reused_ids:
                    old_conflict_stmt = (
                        select(Conflict)
                        .where(
                            Conflict.user_id == user_uuid,
                            Conflict.resolved == False,  # noqa: E712
                        )
                    )
                    old_rows = list((await session.execute(old_conflict_stmt)).scalars().all())
                    for oc in old_rows:
                        if oc.task_ids and set(oc.task_ids) & reused_ids:
                            oc.resolved = True
                            oc.description = f"[auto-superseded] {oc.description or ''}"

                for c in conflicts:
                    ctype = c.get("conflict_type")
                    if not isinstance(ctype, str):
                        continue
                    task_ids: list[uuid.UUID] = []
                    task_title = c.get("task_title")
                    if isinstance(task_title, str) and task_title.strip() in title_to_new_id:
                        task_ids.append(title_to_new_id[task_title.strip()])
                    ref_b = c.get("source_b_ref")
                    if ref_b:
                        existing_tid = _parse_uuid(str(ref_b))
                        if existing_tid:
                            task_ids.append(existing_tid)
                    scope_val = c.get("scope")
                    session.add(
                        Conflict(
                            id=uuid.uuid4(),
                            user_id=user_uuid,
                            conflict_type=ctype,
                            description=c.get("description") if isinstance(c.get("description"), str) else None,
                            source_a_ref=str(c["source_a_ref"]) if c.get("source_a_ref") else None,
                            source_b_ref=str(ref_b) if ref_b else None,
                            task_ids=task_ids or None,
                            scope=scope_val if isinstance(scope_val, str) and scope_val else None,
                        )
                    )

                run.status = "completed"
                run.tasks_extracted = len(saved_task_ids)
                run.conflicts_found = len(conflicts)
                run.completed_at = datetime.now(UTC)
                run.error_message = None

                if doc:
                    doc.processed_at = datetime.now(UTC)
                    doc.pipeline_run_id = run.id

        except Exception as exc:
            errors.append(f"save_tasks failed: {exc}")
            return {"saved_task_ids": [], "errors": errors}

    # Q-05: after a successful persist, seed the user's canonical-by-data pool
    # with the confirmed assignees. We learn AFTER the transaction commits so
    # that a rolled-back save never pollutes the pool with data that was never
    # stored. Abstained tasks are skipped (they were filtered above).
    try:
        resolver = get_default_resolver()
        for vt in validated_tasks:
            if bool(vt.get("abstained")):
                continue
            canonical = vt.get("assignee_canonical")
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            resolver.learn(str(user_uuid), canonical)
    except Exception as exc:
        errors.append(f"save_tasks: assignee_resolver.learn failed: {exc}")

    # Phase 1.2: derive person entities + assigned_to/mentioned_in edges
    # from the just-committed tasks. Best-effort, separate transaction —
    # failures here are logged but never roll back the tasks themselves
    # (entity graph is derived data and re-runnable; idempotent per task).
    try:
        entity_payloads: list[dict] = []
        for vt in validated_tasks:
            if bool(vt.get("abstained")):
                continue
            title = vt.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            tid = title_to_new_id.get(title.strip())
            if tid is None:
                continue
            entity_payloads.append(
                {
                    "id": tid,
                    "title": title,
                    "description": vt.get("description"),
                    "assignee": vt.get("assignee"),
                    "assignee_canonical": vt.get("assignee_canonical"),
                    "evidence_quote": vt.get("evidence_quote"),
                }
            )
        if entity_payloads:
            async with AsyncSessionLocal() as eg_session:
                async with eg_session.begin():
                    await update_entity_graph_for_tasks(
                        eg_session,
                        user_id=user_uuid,
                        tasks=entity_payloads,
                        source_doc_id=source_doc_uuid,
                    )
    except Exception as exc:
        errors.append(f"save_tasks: entity_extractor failed: {exc}")

    return {"saved_task_ids": saved_task_ids, "errors": errors}


def _run_async_save(state: PipelineState) -> dict:
    return asyncio.run(async_save_tasks(state))


def save_tasks_sync(state: PipelineState) -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_async_save(state)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_async_save, state)
        return future.result()
