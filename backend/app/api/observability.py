import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.pipeline_run import PipelineRun
from app.models.sync_state import SyncState
from app.models.task import Task
from app.models.user import User

router = APIRouter()
settings = get_settings()


def _guard_internal_observability(x_internal_token: str | None = Header(default=None)) -> None:
    expected = settings.internal_observability_token
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    idx = int((len(values) - 1) * p)
    return round(values[idx], 2)


async def _langsmith_ingest_block(redis_client) -> dict:
    """Aggregates agent-written LangSmith POST outcomes (global, not per-user)."""
    counts: dict[str, int] = {}
    try:
        raw = await redis_client.hgetall("obs:langsmith:ingest:counts")
        counts = {k: int(v) for k, v in raw.items()}
    except Exception:
        pass
    attempts = counts.get("attempts", 0)
    success = counts.get("success", 0)
    recent: list[dict] = []
    try:
        rows = await redis_client.lrange("obs:langsmith:ingest:events", 0, 9)
        for item in rows:
            try:
                recent.append(json.loads(item))
            except Exception:
                continue
    except Exception:
        pass
    return {
        "counts": counts,
        "failure_rate": round((attempts - success) / attempts, 4) if attempts else 0.0,
        "recent_events": recent,
    }


@router.get("/summary")
async def observability_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_guard_internal_observability),
) -> dict:
    redis_client = await get_redis()
    rows = await redis_client.lrange("obs:llm:calls", 0, 999)
    calls = []
    for raw in rows:
        try:
            item = json.loads(raw)
            # New rows carry user_id; old rows may not. Filter when user_id exists.
            row_uid = item.get("user_id")
            if row_uid is not None and str(row_uid) != str(current_user.id):
                continue
            calls.append(item)
        except Exception:
            continue
    lats = sorted(float(c.get("latency_ms") or 0) for c in calls)
    errors = sum(1 for c in calls if c.get("error"))
    cost_total = round(sum(float(c.get("cost_estimate") or 0) for c in calls), 8)
    token_total = int(sum(int(c.get("total_tokens") or 0) for c in calls))

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=14)
    failed_stmt = select(func.count()).select_from(PipelineRun).where(
        PipelineRun.user_id == current_user.id,
        PipelineRun.started_at >= since,
        PipelineRun.status == "failed",
    )
    total_stmt = select(func.count()).select_from(PipelineRun).where(
        PipelineRun.user_id == current_user.id,
        PipelineRun.started_at >= since,
    )
    missing_deadline_stmt = select(func.count()).select_from(Task).where(
        Task.user_id == current_user.id,
        Task.deadline.is_(None),
    )
    total_task_stmt = select(func.count()).select_from(Task).where(Task.user_id == current_user.id)

    failed = int((await db.execute(failed_stmt)).scalar_one() or 0)
    total_runs = int((await db.execute(total_stmt)).scalar_one() or 0)
    missing_deadline = int((await db.execute(missing_deadline_stmt)).scalar_one() or 0)
    total_tasks = int((await db.execute(total_task_stmt)).scalar_one() or 0)

    langsmith_ingest = await _langsmith_ingest_block(redis_client)

    return {
        "llm": {
            "sample_size": len(calls),
            "error_rate": round(errors / len(calls), 4) if calls else 0.0,
            "p50_ms": _percentile(lats, 0.50),
            "p95_ms": _percentile(lats, 0.95),
            "p99_ms": _percentile(lats, 0.99),
            "total_tokens": token_total,
            "estimated_cost_total": cost_total,
        },
        "pipeline": {
            "window_days": 14,
            "failed_runs": failed,
            "total_runs": total_runs,
            "error_rate": round(failed / total_runs, 4) if total_runs else 0.0,
        },
        "quality": {
            "missing_deadline_tasks": missing_deadline,
            "total_tasks": total_tasks,
            "missing_deadline_rate": round(missing_deadline / total_tasks, 4) if total_tasks else 0.0,
        },
        "targets": {
            "p50_lt_ms": 3000,
            "p95_lt_ms": 10000,
            "p99_lt_ms": 20000,
        },
        "langsmith_ingest": langsmith_ingest,
    }


@router.get("/errors")
async def observability_errors(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_guard_internal_observability),
) -> list[dict]:
    redis_client = await get_redis()
    rows = await redis_client.lrange("obs:pipeline:errors", 0, limit - 1)
    parsed: list[dict] = []
    for raw in rows:
        try:
            item = json.loads(raw)
            if item.get("user_id") == str(current_user.id):
                parsed.append(item)
        except Exception:
            continue
    return parsed


@router.get("/runs")
async def observability_runs(
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_guard_internal_observability),
) -> dict:
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.user_id == current_user.id)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
    )
    runs = list((await db.execute(stmt)).scalars().all())
    if not runs:
        return {"runs": [], "summary": {"count": 0}}

    rows: list[dict] = []
    durations: list[float] = []
    errors = 0
    run_doc_ids = [r.source_doc_id for r in runs if r.source_doc_id is not None]
    totals_by_doc: dict = {}
    missing_by_doc: dict = {}
    if run_doc_ids:
        total_stmt = (
            select(Task.source_doc_id, func.count())
            .where(
                Task.user_id == current_user.id,
                Task.source_doc_id.in_(run_doc_ids),
            )
            .group_by(Task.source_doc_id)
        )
        missing_stmt = (
            select(Task.source_doc_id, func.count())
            .where(
                Task.user_id == current_user.id,
                Task.source_doc_id.in_(run_doc_ids),
                Task.deadline.is_(None),
            )
            .group_by(Task.source_doc_id)
        )
        totals_by_doc = {doc_id: int(cnt or 0) for doc_id, cnt in (await db.execute(total_stmt)).all()}
        missing_by_doc = {doc_id: int(cnt or 0) for doc_id, cnt in (await db.execute(missing_stmt)).all()}

    for run in runs:
        duration_ms = 0.0
        if run.completed_at and run.started_at:
            duration_ms = max((run.completed_at - run.started_at).total_seconds() * 1000, 0.0)
            durations.append(duration_ms)
        if run.status == "failed":
            errors += 1

        total_cnt = int(totals_by_doc.get(run.source_doc_id, 0) or 0)
        missing_cnt = int(missing_by_doc.get(run.source_doc_id, 0) or 0)
        rows.append(
            {
                "pipeline_run_id": str(run.id),
                "status": run.status,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "duration_ms": round(duration_ms, 2),
                "tasks_extracted": run.tasks_extracted,
                "conflicts_found": run.conflicts_found,
                "error_message": run.error_message,
                "quality": {
                    "missing_deadline_tasks": missing_cnt,
                    "total_tasks": total_cnt,
                    "missing_deadline_rate": round(missing_cnt / total_cnt, 4) if total_cnt else 0.0,
                },
            }
        )

    durations_sorted = sorted(durations)
    p50 = _percentile(durations_sorted, 0.50)
    p95 = _percentile(durations_sorted, 0.95)
    p99 = _percentile(durations_sorted, 0.99)
    summary = {
        "count": len(rows),
        "error_rate": round(errors / len(rows), 4),
        "latency_ms": {"p50": p50, "p95": p95, "p99": p99},
        "targets": {"p50_lt_ms": 3000, "p95_lt_ms": 10000, "p99_lt_ms": 20000},
        "target_pass": {"p50": p50 < 3000, "p95": p95 < 10000, "p99": p99 < 20000},
    }
    return {"summary": summary, "runs": rows}


@router.get("/quality")
async def observability_quality(
    window: str | None = Query(
        None,
        pattern=r"^\d+d$",
        description="Rolling window like '30d'. Omit for lifetime aggregate.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_guard_internal_observability),
) -> dict:
    """Section D — task-lifecycle funnel and auto-confirm provenance.

    Driven by a single grouped query over (status, confirmed_by). Both are
    plain TEXT columns, so this avoids the JSONB-null trap that bites
    ``uncertainty IS NULL`` (the column stores a JSON ``null`` literal, which
    is *not* SQL NULL). Auto-confirm provenance lives in ``confirmed_by``:
    ``system`` = auto-confirmed at extraction, ``user`` = manually confirmed,
    NULL = never confirmed. A supersede resets ``status`` to ``pending`` but
    preserves ``confirmed_by``, so ``pending`` + non-null ``confirmed_by``
    marks a task whose prior confirmation was invalidated by a newer message.

    ``window`` (e.g. ``30d``) restricts to tasks created in that rolling
    window. This matters for the auto-confirm rate: the lifetime aggregate is
    diluted by historical content created before auto-confirm existed (those
    tasks can never have ``confirmed_by='system'``), so a windowed rate is the
    honest measure of recent system behaviour. The default is lifetime.
    """
    window_days: int | None = int(window[:-1]) if window else None
    stmt = (
        select(Task.status, Task.confirmed_by, func.count())
        .where(Task.user_id == current_user.id)
        .group_by(Task.status, Task.confirmed_by)
    )
    if window_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = stmt.where(Task.created_at >= since)
    grouped = (await db.execute(stmt)).all()

    crosstab: list[dict] = []
    by_status: dict[str, int] = {}
    by_confirmed_by: dict[str, int] = {"system": 0, "user": 0, "none": 0}
    total = 0
    system_confirmed = 0          # confirmed_by == system, any status
    currently_confirmed_auto = 0  # status == confirmed AND confirmed_by == system
    superseded = 0                # status == pending AND confirmed_by IS NOT NULL
    need_review = 0               # status == pending AND confirmed_by IS NULL

    for status, confirmed_by, count in grouped:
        cnt = int(count or 0)
        total += cnt
        by_status[status] = by_status.get(status, 0) + cnt
        key = confirmed_by if confirmed_by in ("system", "user") else "none"
        by_confirmed_by[key] += cnt
        crosstab.append({"status": status, "confirmed_by": confirmed_by, "count": cnt})

        if confirmed_by == "system":
            system_confirmed += cnt
            if status == "confirmed":
                currently_confirmed_auto += cnt
        if status == "pending":
            if confirmed_by is None:
                need_review += cnt
            else:
                superseded += cnt

    return {
        "window": window,  # null = lifetime; e.g. "30d" = rolling 30-day
        "total_tasks": total,
        "by_status": by_status,
        "by_confirmed_by": by_confirmed_by,
        "crosstab": crosstab,
        "auto_confirm": {
            "system_confirmed": system_confirmed,
            "currently_confirmed_auto": currently_confirmed_auto,
            "user_confirmed": by_confirmed_by["user"],
            "superseded": superseded,
            "need_review": need_review,
            "auto_confirm_rate": round(system_confirmed / total, 4) if total else 0.0,
        },
        "calibration": {
            # ECE needs ground-truth labels (predicted confidence vs actual
            # correctness) and is therefore an offline-eval metric, not a live
            # one. Surfaced as a reference to the eval baseline so the dashboard
            # does not fabricate a runtime number the committee could misread.
            "ece": 0.108,
            "source": "offline_eval_250_sample",
            "note": "ECE requires labeled data; computed offline, not runtime.",
        },
    }


@router.get("/sync-health")
async def observability_sync_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_guard_internal_observability),
) -> dict:
    """Section A — per-source sync state with staleness vs configured interval.

    Adds value over the raw ``/sync/status`` feed by computing how stale each
    source is relative to its configured sync interval. A source is flagged
    stale once it has gone longer than 2x its interval without a successful
    sync (or has never synced).
    """
    interval_by_source = {
        "gmail": settings.sync_gmail_interval_minutes,
        "drive": settings.sync_drive_interval_minutes,
    }
    stmt = select(SyncState).where(SyncState.user_id == current_user.id)
    states = list((await db.execute(stmt)).scalars().all())

    now = datetime.now(timezone.utc)
    sources: list[dict] = []
    any_error = False
    any_stale = False
    for s in states:
        interval = interval_by_source.get(s.source_type, 0)
        staleness_min: float | None = None
        is_stale = True
        if s.last_sync_at is not None:
            last = s.last_sync_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            staleness_min = round((now - last).total_seconds() / 60.0, 1)
            is_stale = interval > 0 and staleness_min > interval * 2
        has_error = bool(s.error_message) or s.status == "error"
        any_error = any_error or has_error
        any_stale = any_stale or is_stale
        sources.append(
            {
                "source_type": s.source_type,
                "status": s.status,
                "last_sync_at": s.last_sync_at,
                "staleness_minutes": staleness_min,
                "interval_minutes": interval,
                "is_stale": is_stale,
                "has_error": has_error,
                "error_message": s.error_message,
            }
        )

    overall = "healthy"
    if any_error:
        overall = "error"
    elif any_stale:
        overall = "stale"
    return {"overall": overall, "sources": sources}
