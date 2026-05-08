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
