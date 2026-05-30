"""Consume sync jobs from Redis ``pipeline:jobs`` and run the LangGraph pipeline."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import redis.asyncio as aioredis
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.mcp.gmail_client import GmailMCPClient
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.models.sync_state import SyncState
from app.pipeline.graph import pipeline
from app.pipeline.llm import collect_provenance
from app.services.observability import record_pipeline_error


async def _find_existing_source_doc(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_ref: str,
) -> SourceDocument | None:
    """Return an existing ``source_documents`` row for this logical source.

    The ``(user_id, source_type, source_ref)`` triple is unique (enforced by
    migration ``0006_source_documents_unique_source_ref``). Callers use this
    helper as the first step of an idempotency check — if the row exists and
    ``processed_at`` is already set, the caller should skip the whole
    pipeline invocation instead of re-running the extraction on an email
    it already processed. Production cross-check (pass 5) showed a single
    Gmail message being ingested 91 times for one user without this guard;
    that multiplied LLM spend and was the dominant driver of chronic 429s.
    """
    if not source_ref:
        return None
    stmt = _select(SourceDocument).where(
        SourceDocument.user_id == user_id,
        SourceDocument.source_type == source_type,
        SourceDocument.source_ref == source_ref,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


from app.services.sync_service import (
    _drive_limit_for_profile,
    _gmail_limit_for_profile,
    pull_recent_drive_files,
    pull_recent_gmail_messages,
)

_pipeline_executor: asyncio.AbstractEventLoop | None = None


def _run_pipeline_in_thread(state: dict) -> dict:
    """Run the synchronous LangGraph pipeline in its own event loop / thread.

    Each invocation opens a fresh :func:`collect_provenance` scope so
    per-call LLM routing (primary vs fallback) can be attributed back to
    this pipeline run. The scope's data is persisted by
    ``record_pipeline_run_trace`` via the validate node; here we just make
    sure every job gets its own isolated scope even under concurrent
    thread dispatch.
    """
    with collect_provenance():
        return pipeline.invoke(state)


async def _invoke_pipeline(state: dict) -> dict:
    return await asyncio.to_thread(_run_pipeline_in_thread, state)


async def _mark_run_failed(run_id: str, error_msg: str = "pipeline exception") -> None:
    """Mark a PipelineRun as failed using a fresh session — safe to call after pipeline errors."""
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                from sqlalchemy import update
                stmt = (
                    update(PipelineRun)
                    .where(PipelineRun.id == uuid.UUID(run_id))
                    .values(status="failed", error_message=error_msg, completed_at=datetime.now(UTC))
                )
                await session.execute(stmt)
    except Exception:
        logger.exception("failed to mark pipeline run %s as failed", run_id)

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=float(settings.redis_socket_connect_timeout_seconds),
        )
        try:
            await asyncio.wait_for(client.ping(), timeout=float(settings.redis_socket_connect_timeout_seconds))
        except Exception as exc:
            logger.error(
                "Redis unreachable at %s (%s). Set REDIS_PUBLISH_PORT or REDIS_URL to the host-published "
                "port from Docker/OrbStack (e.g. mapping 56379:6379 → use 56379 on the host).",
                settings.redis_url,
                type(exc).__name__,
                exc_info=exc,
            )
            raise
        logger.info("Redis queue client connected (%s)", settings.redis_url)
        _redis = client
    return _redis


async def _publish_progress(
    user_id: str, source: str, step: str, detail: str = "", current: int = 0, total: int = 0
) -> None:
    r = await _get_redis()
    key = f"sync:progress:{user_id}:{source}"
    payload = json.dumps(
        {"step": step, "detail": detail, "current": current, "total": total, "ts": datetime.now(UTC).isoformat()}
    )
    await r.set(key, payload, ex=300)


async def _clear_progress(user_id: str, source: str) -> None:
    r = await _get_redis()
    await r.delete(f"sync:progress:{user_id}:{source}")


def _is_auth_revoked_error(error_text: str) -> bool:
    """Return True if the MCP/HTTP error text looks like a user-level token
    revocation (HTTP 401, "invalid_grant", "Invalid Credentials", …).

    These are *user-actionable* — the fix is "reconnect your Google account",
    not "retry later". We treat them separately from transient MCP 5xx or
    network errors so the scheduler can stop the futile 15-minute retry
    loop and surface a clear reconnect signal (Google OAuth docs: revoked
    access tokens continue returning 401 until re-consent; RFC 6819 §5.2.2.2
    recommends graceful degradation, not blind retry).
    """
    if not error_text:
        return False
    t = error_text.lower()
    if "mcp call failed [401]" in t or "http 401" in t or " 401:" in t or "status: 401" in t:
        return True
    return (
        "invalid_grant" in t
        or "invalid credentials" in t
        or "token expired" in t
        or "token revoked" in t
    )


async def _is_sync_disabled_for_auth(user_id: str, source_type: str) -> dict | None:
    """Return the disable-record if the user's auto-sync is suspended because
    of a prior auth-revoked streak, else ``None``."""
    r = await _get_redis()
    raw = await r.get(f"sync:disabled:{user_id}:{source_type}")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


async def _flag_user_auth_revoked(user_id: str, source_type: str, error_text: str) -> None:
    """Increment the 401 streak and, if over threshold, emit a distinct
    ``mcp_auth_revoked`` pipeline error so operators (or the frontend)
    can prompt the user to reconnect. Writing the ``sync:disabled:*`` key is
    handled inside :func:`_record_mcp_auth_outcome`.

    The distinct source_type matters: ``"gmail"``/``"drive"`` 401s were
    historically swallowed as generic sync errors; surfacing them as
    ``"mcp_auth_revoked"`` makes the dashboard counter and the user-visible
    "reconnect Google" banner straightforward without adding a new enum.
    """
    streak, disabled = await _record_mcp_auth_outcome(
        user_id, source_type, auth_error=True
    )
    if disabled:
        record_pipeline_error(
            source_type="mcp_auth_revoked",
            user_id=user_id,
            error=(
                f"{source_type}: auth 401 streak={streak} "
                f">= threshold={settings.mcp_auth_revoke_streak_threshold}; "
                f"auto-sync suspended for {source_type} until reconnect. "
                f"last_error={error_text[:160]}"
            ),
        )


async def _record_mcp_auth_outcome(
    user_id: str,
    source_type: str,
    *,
    auth_error: bool,
) -> tuple[int, bool]:
    """Track consecutive MCP 401 outcomes per user and return
    ``(streak_after, should_disable_sync)``.

    Design:
    - Each sync attempt either *succeeds authenticating* (``auth_error=False``,
      clearing the streak) or *fails with an auth-class error* (``auth_error=
      True``, incrementing the streak).
    - When the streak reaches ``settings.mcp_auth_revoke_streak_threshold``,
      the caller should (a) emit a distinct ``source_type="mcp_auth_revoked"``
      pipeline error so dashboards/UI can pick it up and prompt reconnection,
      and (b) write a time-bounded flag that ``_get_sync_eligible_users`` will
      honor to skip the user until re-auth.
    - We use per-(user, source) keys so Gmail and Drive are tracked
      independently — Google can revoke one scope without the other (rare but
      observed).
    - TTL on the streak key prevents an abandoned account from accumulating
      "forever" — after a quiet day the counter resets.
    """
    r = await _get_redis()
    streak_key = f"mcp:auth_streak:{user_id}:{source_type}"
    if not auth_error:
        await r.delete(streak_key)
        return 0, False
    new_val = await r.incr(streak_key)
    await r.expire(streak_key, max(settings.mcp_auth_revoke_disable_ttl_seconds, 3600))
    threshold = max(settings.mcp_auth_revoke_streak_threshold, 1)
    should_disable = int(new_val) >= threshold
    if should_disable:
        disable_key = f"sync:disabled:{user_id}:{source_type}"
        await r.set(
            disable_key,
            json.dumps(
                {
                    "reason": "mcp_auth_revoked",
                    "since": datetime.now(UTC).isoformat(),
                    "streak": int(new_val),
                    "source_type": source_type,
                }
            ),
            ex=max(settings.mcp_auth_revoke_disable_ttl_seconds, 3600),
        )
    return int(new_val), should_disable


_DAILY_QUOTA_MARKERS = ("tokens per day", "(tpd)", "requests per day", "(rpd)")


def _is_daily_quota_error_text(error_text: str) -> bool:
    t = (error_text or "").lower()
    return any(marker in t for marker in _DAILY_QUOTA_MARKERS)


async def _llm_pressure_snapshot() -> tuple[bool, float, int, bool]:
    """Return (high_pressure, ratio, sample_size, daily_quota_exhausted).

    ``daily_quota_exhausted`` is True when the recent obs:llm:calls window
    is saturated with TPD/RPD 429s. Those reset only at 00:00 UTC so a
    minute-scale requeue is pointless — callers should defer the job to the
    day boundary (or fail the sync cleanly) instead of churning in a retry
    loop that burns Redis cycles and never recovers.

    Entries older than the current UTC day are excluded: TPD/RPD quotas reset
    at UTC midnight, so yesterday's errors must not block today's syncs even
    when those entries happen to be at the head of the Redis list.
    """

    r = await _get_redis()
    window = max(settings.llm_pressure_window_size, 1)
    # Read a larger buffer so date-filtering doesn't silently under-sample
    # when today has fewer than ``window`` entries yet.
    rows = await r.lrange("obs:llm:calls", 0, window * 4 - 1)
    if not rows:
        return False, 0.0, 0, False

    utc_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    rate_limit_errors = 0
    daily_errors = 0
    valid = 0
    for row in rows:
        if valid >= window:
            break
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        # Skip entries from a previous UTC day — TPD/RPD already reset.
        ts_raw = payload.get("ts") or ""
        if ts_raw:
            try:
                entry_ts = datetime.fromisoformat(str(ts_raw))
                if entry_ts.tzinfo is None:
                    entry_ts = entry_ts.replace(tzinfo=UTC)
                if entry_ts < utc_today:
                    continue
            except (ValueError, TypeError):
                pass  # unparseable ts → include conservatively
        valid += 1
        error = str(payload.get("error") or "").lower()
        if "429" in error or "rate limit" in error or "rate_limit" in error:
            rate_limit_errors += 1
            kind = (payload.get("rate_limit_kind") or "").lower()
            if kind in {"tpd", "rpd"} or _is_daily_quota_error_text(error):
                daily_errors += 1
    if valid == 0:
        return False, 0.0, 0, False
    ratio = rate_limit_errors / valid
    high = ratio >= settings.llm_rate_limit_error_threshold
    # Require both a meaningful sample AND a majority-daily share so a
    # single stale TPD record can't freeze ingestion. Threshold mirrors the
    # fallback routing rule — if >=50% of recent rate-limited calls are
    # daily-window, in-process retry is a waste.
    daily_exhausted = (
        high
        and valid >= max(5, window // 4)
        and rate_limit_errors > 0
        and daily_errors / rate_limit_errors >= 0.5
    )
    return high, ratio, valid, daily_exhausted


async def _requeue_deferred_job(job: dict, deferred: int) -> None:
    retry_count = int(job.get("retry_count", 0))
    if retry_count >= settings.llm_pressure_requeue_max_retries:
        logger.warning(
            "skip deferred requeue: reached retry cap (%s), source=%s, user=%s, deferred=%s",
            retry_count,
            job.get("source_type"),
            job.get("user_id"),
            deferred,
        )
        return

    requeue_job = dict(job)
    requeue_job["retry_count"] = retry_count + 1
    requeue_job["triggered_by"] = "throttled_retry"
    requeue_job["deferred_count_hint"] = deferred
    delay = max(settings.llm_pressure_requeue_delay_seconds, 0.0)
    if delay > 0:
        await asyncio.sleep(delay)
    r = await _get_redis()
    await r.lpush(settings.pipeline_queue_name, json.dumps(requeue_job))
    logger.info(
        "requeued deferred job: source=%s user=%s deferred=%s retry=%s delay=%.1fs",
        requeue_job.get("source_type"),
        requeue_job.get("user_id"),
        deferred,
        requeue_job["retry_count"],
        delay,
    )


async def _ensure_sync_state(user_id: uuid.UUID, source_type: str, status: str, error: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            from sqlalchemy import select

            stmt = select(SyncState).where(SyncState.user_id == user_id, SyncState.source_type == source_type)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                row = SyncState(id=uuid.uuid4(), user_id=user_id, source_type=source_type)
                session.add(row)
            row.status = status
            if status in ("idle", "error"):
                row.last_sync_at = datetime.now(UTC)
            if error:
                row.error_message = error
            elif status != "error":
                row.error_message = None


_TIME_RANGE_MAP: dict[str, timedelta] = {
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _time_range_to_datetime(time_range: str) -> datetime:
    delta = _TIME_RANGE_MAP.get(time_range, timedelta(days=1))
    return datetime.now(UTC) - delta


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _extract_drive_raw_content(content: str | bytes | dict | None) -> str | bytes | None:
    if content is None:
        return None
    if isinstance(content, (str, bytes)):
        return content
    if not isinstance(content, dict):
        return None
    b64 = content.get("content_base64")
    if isinstance(b64, str) and b64.strip():
        try:
            decoded = base64.b64decode(b64, validate=True)
            if not decoded:
                return None
            return decoded
        except Exception:
            return None
    for key in ("content", "text", "data"):
        value = content.get(key)
        if isinstance(value, (str, bytes)) and value:
            return value
    return None


def _parse_gmail_message(full: dict | str, msg: dict) -> dict | None:
    """Extract body, subject, sender, thread_id from a fetched Gmail message."""
    body = ""
    if isinstance(full, dict):
        body = full.get("body") or full.get("html") or full.get("snippet") or ""
    elif isinstance(full, str):
        body = full
    if not body:
        return None

    msg_id = msg.get("id") or msg.get("message_id") or ""
    thread_id = ""
    subject = ""
    sender = ""
    sent_at = ""
    if isinstance(full, dict):
        thread_id = full.get("threadId") or msg.get("threadId") or msg.get("thread_id") or msg_id
        headers = full.get("headers") or full.get("payload", {}).get("headers") or []
        if isinstance(headers, list):
            for h in headers:
                name = (h.get("name") or "").lower()
                if name == "subject":
                    subject = h.get("value", "")
                elif name == "from":
                    sender = h.get("value", "")
                elif name == "date":
                    sent_at = h.get("value", "")
        if not subject:
            subject = full.get("subject", "")
        if not sender:
            sender = full.get("from", "")
        if not sent_at:
            sent_at = full.get("date", "")
    if not thread_id:
        thread_id = msg.get("threadId") or msg.get("thread_id") or msg_id

    sent_at_iso = ""
    internal_date = ""
    if sent_at:
        try:
            sent_at_iso = parsedate_to_datetime(sent_at).astimezone(UTC).isoformat()
        except Exception:
            sent_at_iso = ""
    if isinstance(full, dict):
        internal_date = str(full.get("internalDate") or msg.get("internalDate") or "").strip()
    if not sent_at_iso and internal_date.isdigit():
        try:
            sent_at_iso = datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC).isoformat()
        except Exception:
            sent_at_iso = ""

    return {
        "body": body,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "sent_at": sent_at_iso,
        "msg_id": msg_id,
    }


_FETCH_CONCURRENCY = 5


async def _process_gmail_job(
    user_id: str,
    access_token: str,
    time_range: str = "1d",
    sync_profile: str = "balanced",
    raw_job: dict | None = None,
) -> None:
    uid = uuid.UUID(user_id)
    profile_limit = _gmail_limit_for_profile(sync_profile)
    disabled = await _is_sync_disabled_for_auth(user_id, "gmail")
    if disabled and str(disabled.get("reason")) == "mcp_auth_revoked":
        logger.info(
            "gmail sync: skipping user %s — auth_revoked since %s",
            user_id,
            disabled.get("since"),
        )
        await _ensure_sync_state(
            uid,
            "gmail",
            "error",
            f"mcp_auth_revoked: reconnect Google account (since {disabled.get('since')})",
        )
        await _publish_progress(
            user_id,
            "gmail",
            "error",
            "Google authorization was revoked — reconnect in Settings to resume sync",
        )
        return
    await _ensure_sync_state(uid, "gmail", "running")
    await _publish_progress(
        user_id,
        "gmail",
        "connecting",
        f"Connecting to Gmail (last {time_range}, profile={sync_profile}, cap={profile_limit})",
    )

    last_sync_at = _time_range_to_datetime(time_range)
    error_msg: str | None = None
    try:
        messages = await pull_recent_gmail_messages(
            user_id=user_id,
            access_token=access_token,
            last_sync_at=last_sync_at,
            sync_profile=sync_profile,
        )
        if not messages:
            logger.info("gmail sync: no new messages for user %s", user_id)
            await _publish_progress(user_id, "gmail", "done", "No new messages found")
            return

        total = len(messages)
        await _publish_progress(user_id, "gmail", "fetching", f"Fetching {total} messages", 0, total)

        gmail = GmailMCPClient(access_token=access_token)
        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def fetch_one(m: dict) -> tuple[dict, dict | str | None]:
            mid = m.get("id") or m.get("message_id") or ""
            if not mid:
                return m, None
            async with sem:
                try:
                    return m, await gmail.get_message(str(mid))
                except Exception:
                    logger.warning("gmail: failed to fetch message %s", mid)
                    return m, None

        fetched = await asyncio.gather(*(fetch_one(m) for m in messages))
        await _publish_progress(user_id, "gmail", "processing", f"Processing {total} messages", 0, total)

        processed = 0
        skipped_dedup = 0
        failed_docs = 0
        (
            llm_pressure_high,
            pressure_ratio,
            pressure_sample_size,
            daily_quota_exhausted,
        ) = await _llm_pressure_snapshot()
        max_docs_under_pressure = max(settings.llm_pressure_max_documents_per_job, 1)
        deferred = 0
        # Daily quotas won't reset until the next UTC midnight. A minute-scale
        # requeue loop is guaranteed to fail the same way; skip the sync
        # cleanly and let sync_state carry a diagnostic the UI can render.
        if daily_quota_exhausted:
            error_msg = (
                f"llm_daily_quota_exhausted: {pressure_ratio:.0%} rate-limited "
                f"(TPD/RPD) in last {pressure_sample_size} calls; sync will "
                f"retry after the next UTC day boundary"
            )
            logger.warning("gmail sync: %s (user=%s)", error_msg, user_id)
            await _publish_progress(user_id, "gmail", "throttling", error_msg, 0, total)
            return
        if llm_pressure_high:
            await _publish_progress(
                user_id,
                "gmail",
                "throttling",
                f"LLM pressure high ({pressure_ratio:.0%} in last {pressure_sample_size}); deferring after {max_docs_under_pressure} docs",
                0,
                total,
            )
        for idx, (msg, full) in enumerate(fetched):
            if full is None:
                continue
            parsed = _parse_gmail_message(full, msg)
            if parsed is None:
                continue
            if llm_pressure_high and processed >= max_docs_under_pressure:
                deferred += 1
                continue

            body_html = parsed["body"]
            chash = _content_hash(body_html if isinstance(body_html, str) else str(body_html))
            msg_ref = str(parsed["msg_id"])

            doc_id_val: uuid.UUID | None = None
            run_id_val: uuid.UUID | None = None
            skip_pipeline = False
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    existing = await _find_existing_source_doc(
                        session, user_id=uid, source_type="gmail", source_ref=msg_ref
                    )
                    if existing is not None:
                        doc_id_val = existing.id
                        if existing.processed_at is not None:
                            skip_pipeline = True
                        else:
                            run_id_val = uuid.uuid4()
                            session.add(
                                PipelineRun(
                                    id=run_id_val,
                                    user_id=uid,
                                    source_doc_id=doc_id_val,
                                    status="running",
                                )
                            )
                    else:
                        doc_id_val = uuid.uuid4()
                        run_id_val = uuid.uuid4()
                        # Persist Gmail's parsed Date: / internalDate as received_at
                        # so the task-detail Source panel can show when the email
                        # actually arrived (not when TaskBot synced it). See
                        # migration 0012. Empty string from _parse_gmail_message
                        # means parsing failed — leave NULL in that case.
                        sent_at_raw = parsed.get("sent_at") if isinstance(parsed, dict) else None
                        received_at_dt = None
                        if isinstance(sent_at_raw, str) and sent_at_raw:
                            try:
                                received_at_dt = datetime.fromisoformat(sent_at_raw)
                            except ValueError:
                                received_at_dt = None
                        doc = SourceDocument(
                            id=doc_id_val,
                            user_id=uid,
                            source_type="gmail",
                            source_ref=msg_ref,
                            dedupe_group_id=str(parsed["thread_id"]),
                            content_hash=chash,
                            raw_text=body_html[:50_000] if isinstance(body_html, str) else None,
                            received_at=received_at_dt,
                        )
                        session.add(doc)
                        await session.flush()
                        session.add(
                            PipelineRun(
                                id=run_id_val,
                                user_id=uid,
                                source_doc_id=doc_id_val,
                                status="running",
                            )
                        )

            if skip_pipeline:
                skipped_dedup += 1
                logger.info(
                    "gmail sync: skip already-processed msg=%s doc=%s",
                    msg_ref,
                    doc_id_val,
                )
                continue

            doc_id = str(doc_id_val)
            run_id = str(run_id_val) if run_id_val is not None else ""

            processed += 1
            await _publish_progress(user_id, "gmail", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                "content_hash": chash, "source_type": "gmail", "raw_content": body_html,
                "metadata": {
                    "subject": parsed["subject"],
                    "sender": parsed["sender"],
                    "sent_at": parsed["sent_at"],
                    "sync_profile": sync_profile,
                    "dedupe_group_id": str(parsed["thread_id"]),
                },
            }
            try:
                await _invoke_pipeline(state)
                logger.info("gmail pipeline ok: msg=%s doc=%s", parsed["msg_id"], doc_id)
            except Exception as exc:
                logger.exception("gmail pipeline failed: msg=%s", parsed["msg_id"])
                failed_docs += 1
                await _mark_run_failed(run_id, error_msg=str(exc)[:500])
                record_pipeline_error(
                    source_type="gmail",
                    user_id=user_id,
                    error=f"doc={doc_id}: {str(exc)[:400]}",
                )
                err = str(exc).lower()
                if "429" in err or "rate limit" in err or "rate_limit" in err:
                    remaining = max(total - (idx + 1), 0)
                    deferred += remaining
                    await _publish_progress(
                        user_id,
                        "gmail",
                        "throttling",
                        f"LLM rate-limited mid-run; deferred {remaining} remaining messages",
                        processed,
                        total,
                    )
                    break
            await asyncio.sleep(max(settings.llm_per_document_cooldown_seconds, 0.0))

        detail = f"Completed — processed {processed} messages"
        if skipped_dedup:
            detail = f"{detail}, skipped {skipped_dedup} already-processed"
        if deferred:
            detail = f"{detail}, deferred {deferred} due to LLM pressure"
            if raw_job is not None:
                asyncio.create_task(_requeue_deferred_job(raw_job, deferred))
        if failed_docs and error_msg is None:
            error_msg = f"partial_failure: {failed_docs}/{total} documents failed"
        await _publish_progress(user_id, "gmail", "done", detail, processed, total)
    except Exception as exc:
        logger.exception("gmail sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        auth_error = _is_auth_revoked_error(error_msg)
        record_pipeline_error(source_type="gmail", user_id=user_id, error=error_msg)
        if auth_error:
            await _flag_user_auth_revoked(user_id, "gmail", error_msg)
        await _publish_progress(user_id, "gmail", "error", str(exc)[:200])
    else:
        await _record_mcp_auth_outcome(user_id, "gmail", auth_error=False)
    finally:
        if error_msg:
            await _ensure_sync_state(uid, "gmail", "error", error_msg)
        else:
            await _ensure_sync_state(uid, "gmail", "idle")
        await _clear_progress(user_id, "gmail")


async def _process_drive_job(
    user_id: str,
    access_token: str,
    time_range: str = "1d",
    sync_profile: str = "balanced",
    raw_job: dict | None = None,
) -> None:
    uid = uuid.UUID(user_id)
    profile_limit = _drive_limit_for_profile(sync_profile)
    disabled = await _is_sync_disabled_for_auth(user_id, "drive")
    if disabled and str(disabled.get("reason")) == "mcp_auth_revoked":
        logger.info(
            "drive sync: skipping user %s — auth_revoked since %s",
            user_id,
            disabled.get("since"),
        )
        await _ensure_sync_state(
            uid,
            "drive",
            "error",
            f"mcp_auth_revoked: reconnect Google account (since {disabled.get('since')})",
        )
        await _publish_progress(
            user_id,
            "drive",
            "error",
            "Google authorization was revoked — reconnect in Settings to resume sync",
        )
        return
    await _ensure_sync_state(uid, "drive", "running")
    await _publish_progress(
        user_id,
        "drive",
        "connecting",
        f"Connecting to Google Drive (last {time_range}, profile={sync_profile}, cap={profile_limit})",
    )

    last_sync_at = _time_range_to_datetime(time_range)
    error_msg: str | None = None
    try:
        files = await pull_recent_drive_files(
            user_id=user_id,
            access_token=access_token,
            last_sync_at=last_sync_at,
            sync_profile=sync_profile,
        )
        if not files:
            logger.info("drive sync: no new files for user %s", user_id)
            await _publish_progress(user_id, "drive", "done", "No new files found")
            return

        total = len(files)
        await _publish_progress(user_id, "drive", "fetching", f"Fetching {total} files", 0, total)

        from app.mcp.drive_client import DriveMCPClient
        drive = DriveMCPClient(access_token=access_token)
        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def fetch_one(f_item: dict) -> tuple[dict, str | bytes | dict | None]:
            fid = f_item.get("id") or ""
            if not fid:
                return f_item, None
            async with sem:
                try:
                    return f_item, await drive.get_file_content(fid)
                except Exception:
                    logger.warning("drive: failed to fetch file %s", fid)
                    return f_item, None

        fetched = await asyncio.gather(*(fetch_one(f) for f in files))
        await _publish_progress(user_id, "drive", "processing", f"Processing {total} files", 0, total)

        processed = 0
        skipped_dedup = 0
        failed_docs = 0
        (
            llm_pressure_high,
            pressure_ratio,
            pressure_sample_size,
            daily_quota_exhausted,
        ) = await _llm_pressure_snapshot()
        max_docs_under_pressure = max(settings.llm_pressure_max_documents_per_job, 1)
        deferred = 0
        if daily_quota_exhausted:
            error_msg = (
                f"llm_daily_quota_exhausted: {pressure_ratio:.0%} rate-limited "
                f"(TPD/RPD) in last {pressure_sample_size} calls; sync will "
                f"retry after the next UTC day boundary"
            )
            logger.warning("drive sync: %s (user=%s)", error_msg, user_id)
            await _publish_progress(user_id, "drive", "throttling", error_msg, 0, total)
            return
        if llm_pressure_high:
            await _publish_progress(
                user_id,
                "drive",
                "throttling",
                f"LLM pressure high ({pressure_ratio:.0%} in last {pressure_sample_size}); deferring after {max_docs_under_pressure} docs",
                0,
                total,
            )
        for idx, (f_item, content) in enumerate(fetched):
            file_id = f_item.get("id") or ""
            file_name = f_item.get("name") or "unknown"
            raw = _extract_drive_raw_content(content)
            if raw is None:
                continue
            if llm_pressure_high and processed >= max_docs_under_pressure:
                deferred += 1
                continue

            chash = _content_hash(raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace"))

            doc_id_val: uuid.UUID | None = None
            run_id_val: uuid.UUID | None = None
            skip_pipeline = False
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    existing = await _find_existing_source_doc(
                        session, user_id=uid, source_type="drive", source_ref=file_id
                    )
                    if existing is not None:
                        doc_id_val = existing.id
                        if existing.processed_at is not None:
                            skip_pipeline = True
                        else:
                            run_id_val = uuid.uuid4()
                            session.add(
                                PipelineRun(
                                    id=run_id_val,
                                    user_id=uid,
                                    source_doc_id=doc_id_val,
                                    status="running",
                                )
                            )
                    else:
                        doc_id_val = uuid.uuid4()
                        run_id_val = uuid.uuid4()
                        doc = SourceDocument(
                            id=doc_id_val,
                            user_id=uid,
                            source_type="drive",
                            source_ref=file_id,
                            dedupe_group_id=file_id,
                            content_hash=chash,
                            raw_text=raw[:50_000] if isinstance(raw, str) else None,
                        )
                        session.add(doc)
                        await session.flush()
                        session.add(
                            PipelineRun(
                                id=run_id_val,
                                user_id=uid,
                                source_doc_id=doc_id_val,
                                status="running",
                            )
                        )

            if skip_pipeline:
                skipped_dedup += 1
                logger.info(
                    "drive sync: skip already-processed file=%s doc=%s",
                    file_id,
                    doc_id_val,
                )
                continue

            doc_id = str(doc_id_val)
            run_id = str(run_id_val) if run_id_val is not None else ""

            processed += 1
            await _publish_progress(user_id, "drive", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                "content_hash": chash, "source_type": "drive", "raw_content": raw,
                "metadata": {"file_name": file_name, "sync_profile": sync_profile, "dedupe_group_id": file_id},
            }
            try:
                await _invoke_pipeline(state)
                logger.info("drive pipeline ok: file=%s doc=%s", file_id, doc_id)
            except Exception as exc:
                logger.exception("drive pipeline failed: file=%s", file_id)
                failed_docs += 1
                await _mark_run_failed(run_id, error_msg=str(exc)[:500])
                record_pipeline_error(
                    source_type="drive",
                    user_id=user_id,
                    error=f"doc={doc_id}: {str(exc)[:400]}",
                )
                err = str(exc).lower()
                if "429" in err or "rate limit" in err or "rate_limit" in err:
                    remaining = max(total - (idx + 1), 0)
                    deferred += remaining
                    await _publish_progress(
                        user_id,
                        "drive",
                        "throttling",
                        f"LLM rate-limited mid-run; deferred {remaining} remaining files",
                        processed,
                        total,
                    )
                    break
            await asyncio.sleep(max(settings.llm_per_document_cooldown_seconds, 0.0))

        detail = f"Completed — processed {processed} files"
        if skipped_dedup:
            detail = f"{detail}, skipped {skipped_dedup} already-processed"
        if deferred:
            detail = f"{detail}, deferred {deferred} due to LLM pressure"
            if raw_job is not None:
                asyncio.create_task(_requeue_deferred_job(raw_job, deferred))
        if failed_docs and error_msg is None:
            error_msg = f"partial_failure: {failed_docs}/{total} documents failed"
        await _publish_progress(user_id, "drive", "done", detail, processed, total)
    except Exception as exc:
        logger.exception("drive sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        auth_error = _is_auth_revoked_error(error_msg)
        record_pipeline_error(source_type="drive", user_id=user_id, error=error_msg)
        if auth_error:
            await _flag_user_auth_revoked(user_id, "drive", error_msg)
        await _publish_progress(user_id, "drive", "error", str(exc)[:200])
    else:
        await _record_mcp_auth_outcome(user_id, "drive", auth_error=False)
    finally:
        if error_msg:
            await _ensure_sync_state(uid, "drive", "error", error_msg)
        else:
            await _ensure_sync_state(uid, "drive", "idle")
        await _clear_progress(user_id, "drive")


_CALENDAR_RESYNC_MAX_ATTEMPTS = 3
_CALENDAR_RESYNC_RETRY_DELAY_SECONDS = 2.0


async def _process_calendar_resync_job(user_id: str, access_token: str, task_id: str) -> None:
    """Update the Google Calendar event for a single task after a conflict merge.

    Reuses ``async_dispatch_notifications`` (which is idempotent — it calls
    ``update_event`` when the task already has a ``calendar_event_id``). The
    backend only enqueues this job when the surviving task HAS a calendar event
    and a calendar-reflected field changed, so the dispatch always lands on the
    update path, never create.

    In-handler bounded retry covers transient MCP/network blips. Auth-class
    failures (401/invalid_grant) are user-actionable — surfaced via
    ``record_pipeline_error`` and never retried (a revoked token won't recover
    on its own).
    """
    from app.services.notification_service import async_dispatch_notifications

    for attempt in range(1, _CALENDAR_RESYNC_MAX_ATTEMPTS + 1):
        state = {
            "user_id": user_id,
            "access_token": access_token,
            "saved_task_ids": [task_id],
        }
        result = await async_dispatch_notifications(state)
        task_errors = [e for e in result.get("errors", []) if task_id in e]
        if not task_errors:
            logger.info("calendar_resync ok: task=%s (attempt %s)", task_id, attempt)
            return
        joined = " ".join(task_errors)
        if _is_auth_revoked_error(joined) or " 403" in joined or "[403]" in joined:
            record_pipeline_error(
                source_type="calendar_resync",
                user_id=user_id,
                error=f"task={task_id}: permanent calendar failure, not retrying: {joined[:300]}",
            )
            return
        if attempt < _CALENDAR_RESYNC_MAX_ATTEMPTS:
            logger.warning(
                "calendar_resync transient failure task=%s attempt=%s; retrying: %s",
                task_id, attempt, joined[:200],
            )
            await asyncio.sleep(_CALENDAR_RESYNC_RETRY_DELAY_SECONDS)
    record_pipeline_error(
        source_type="calendar_resync",
        user_id=user_id,
        error=f"task={task_id}: exhausted {_CALENDAR_RESYNC_MAX_ATTEMPTS} attempts",
    )


async def _process_weekly_brief_job(user_id: str, access_token: str) -> None:
    """Build and self-send the manager's Weekly Brief (Phase 8.3).

    Fail-safe like calendar dispatch: a missing gmail.send scope yields a 403
    which ``async_send_weekly_brief`` returns as an error rather than raising.
    We record it (user-actionable: reconnect for send permission) and move on.
    """
    from app.services.weekly_brief_service import async_send_weekly_brief

    result = await async_send_weekly_brief(user_id, access_token)
    if result.get("sent"):
        logger.info("weekly_brief ok: user=%s", user_id)
        return
    errors = result.get("errors") or ["unknown failure"]
    record_pipeline_error(
        source_type="weekly_brief",
        user_id=user_id,
        error="; ".join(errors)[:300],
    )


async def _process_daily_digest_job(user_id: str, access_token: str) -> None:
    """Build and self-send the Daily Digest (Round 9, 2026-05-30).

    Sibling of ``_process_weekly_brief_job`` — same fail-safe semantics:
    missing gmail.send scope yields a 403 which is recorded, not raised.
    """
    from app.services.daily_digest_service import async_send_daily_digest

    result = await async_send_daily_digest(user_id, access_token)
    if result.get("sent"):
        logger.info("daily_digest ok: user=%s", user_id)
        return
    errors = result.get("errors") or ["unknown failure"]
    record_pipeline_error(
        source_type="daily_digest",
        user_id=user_id,
        error="; ".join(errors)[:300],
    )


async def consume_pipeline_jobs() -> None:
    """BLPOP loop: pick jobs from ``pipeline:jobs`` and dispatch."""
    r = await _get_redis()
    queue = settings.pipeline_queue_name
    logger.info("queue consumer started — listening on '%s'", queue)

    while True:
        try:
            result = await r.blpop(queue, timeout=5)
            if result is None:
                continue
            _, raw = result
            job = json.loads(raw)
            user_id = job.get("user_id", "")
            source = job.get("source_type", "")
            token = job.get("access_token", "")
            if not user_id or not token:
                logger.warning("invalid job payload, skipping: %s", raw[:200])
                continue

            if source == "calendar_resync":
                task_id = job.get("task_id", "")
                if not task_id:
                    logger.warning("calendar_resync job missing task_id, skipping")
                    continue
                logger.info("processing calendar_resync job for user %s task %s", user_id, task_id)
                await _process_calendar_resync_job(user_id, token, task_id)
                continue

            if source == "weekly_brief":
                logger.info("processing weekly_brief job for user %s", user_id)
                await _process_weekly_brief_job(user_id, token)
                continue

            if source == "daily_digest":
                logger.info("processing daily_digest job for user %s", user_id)
                await _process_daily_digest_job(user_id, token)
                continue

            time_range = job.get("time_range", "1d")
            sync_profile = job.get("sync_profile", "balanced")
            logger.info(
                "processing %s sync job for user %s (range=%s, profile=%s)",
                source,
                user_id,
                time_range,
                sync_profile,
            )
            if source == "gmail":
                await _process_gmail_job(user_id, token, time_range, sync_profile, raw_job=job)
            elif source == "drive":
                await _process_drive_job(user_id, token, time_range, sync_profile, raw_job=job)
            else:
                logger.warning("unknown source_type '%s', skipping", source)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("queue consumer iteration error")
            await asyncio.sleep(2)
