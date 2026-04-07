"""Consume sync jobs from Redis ``pipeline:jobs`` and run the LangGraph pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.mcp.gmail_client import GmailMCPClient
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.models.sync_state import SyncState
from app.pipeline.graph import pipeline
from app.services.sync_service import pull_recent_drive_files, pull_recent_gmail_messages

_pipeline_executor: asyncio.AbstractEventLoop | None = None


def _run_pipeline_in_thread(state: dict) -> dict:
    """Run the synchronous LangGraph pipeline in its own event loop / thread."""
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
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
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
        if not subject:
            subject = full.get("subject", "")
        if not sender:
            sender = full.get("from", "")
    if not thread_id:
        thread_id = msg.get("threadId") or msg.get("thread_id") or msg_id

    return {"body": body, "thread_id": thread_id, "subject": subject, "sender": sender, "msg_id": msg_id}


_FETCH_CONCURRENCY = 5


async def _process_gmail_job(user_id: str, access_token: str, time_range: str = "1d") -> None:
    uid = uuid.UUID(user_id)
    await _ensure_sync_state(uid, "gmail", "running")
    await _publish_progress(user_id, "gmail", "connecting", f"Connecting to Gmail (last {time_range})")

    last_sync_at = _time_range_to_datetime(time_range)
    error_msg: str | None = None
    try:
        messages = await pull_recent_gmail_messages(user_id=user_id, access_token=access_token, last_sync_at=last_sync_at)
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
        for idx, (msg, full) in enumerate(fetched):
            if full is None:
                continue
            parsed = _parse_gmail_message(full, msg)
            if parsed is None:
                continue

            body_html = parsed["body"]
            chash = _content_hash(body_html if isinstance(body_html, str) else str(body_html))

            doc_id_val = uuid.uuid4()
            run_id_val = uuid.uuid4()
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    doc = SourceDocument(
                        id=doc_id_val, user_id=uid, source_type="gmail",
                        source_ref=str(parsed["msg_id"]),
                        dedupe_group_id=str(parsed["thread_id"]),
                        content_hash=chash,
                        raw_text=body_html[:50_000] if isinstance(body_html, str) else None,
                    )
                    session.add(doc)
                    await session.flush()
                    session.add(PipelineRun(id=run_id_val, user_id=uid, source_doc_id=doc_id_val, status="running"))
            doc_id = str(doc_id_val)
            run_id = str(run_id_val)

            processed += 1
            await _publish_progress(user_id, "gmail", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                "content_hash": chash, "source_type": "gmail", "raw_content": body_html,
                "metadata": {"subject": parsed["subject"], "sender": parsed["sender"], "dedupe_group_id": str(parsed["thread_id"])},
            }
            try:
                await _invoke_pipeline(state)
                logger.info("gmail pipeline ok: msg=%s doc=%s", parsed["msg_id"], doc_id)
            except Exception:
                logger.exception("gmail pipeline failed: msg=%s", parsed["msg_id"])
                await _mark_run_failed(run_id)

        await _publish_progress(user_id, "gmail", "done", f"Completed — processed {processed} messages", total, total)
    except Exception as exc:
        logger.exception("gmail sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        await _publish_progress(user_id, "gmail", "error", str(exc)[:200])
    finally:
        if error_msg:
            await _ensure_sync_state(uid, "gmail", "error", error_msg)
        else:
            await _ensure_sync_state(uid, "gmail", "idle")
        await _clear_progress(user_id, "gmail")


async def _process_drive_job(user_id: str, access_token: str, time_range: str = "1d") -> None:
    uid = uuid.UUID(user_id)
    await _ensure_sync_state(uid, "drive", "running")
    await _publish_progress(user_id, "drive", "connecting", f"Connecting to Google Drive (last {time_range})")

    last_sync_at = _time_range_to_datetime(time_range)
    error_msg: str | None = None
    try:
        files = await pull_recent_drive_files(user_id=user_id, access_token=access_token, last_sync_at=last_sync_at)
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
        for idx, (f_item, content) in enumerate(fetched):
            file_id = f_item.get("id") or ""
            file_name = f_item.get("name") or "unknown"
            if content is None:
                continue

            raw: str | bytes = ""
            if isinstance(content, dict):
                raw = content.get("content") or content.get("text") or content.get("data") or ""
            elif isinstance(content, (str, bytes)):
                raw = content
            if not raw:
                continue

            chash = _content_hash(raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace"))
            doc_id_val = uuid.uuid4()
            run_id_val = uuid.uuid4()
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    doc = SourceDocument(
                        id=doc_id_val, user_id=uid, source_type="drive",
                        source_ref=file_id, dedupe_group_id=file_id,
                        content_hash=chash,
                        raw_text=raw[:50_000] if isinstance(raw, str) else None,
                    )
                    session.add(doc)
                    await session.flush()
                    session.add(PipelineRun(id=run_id_val, user_id=uid, source_doc_id=doc_id_val, status="running"))
            doc_id = str(doc_id_val)
            run_id = str(run_id_val)

            processed += 1
            await _publish_progress(user_id, "drive", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                "content_hash": chash, "source_type": "drive", "raw_content": raw,
                "metadata": {"file_name": file_name, "dedupe_group_id": file_id},
            }
            try:
                await _invoke_pipeline(state)
                logger.info("drive pipeline ok: file=%s doc=%s", file_id, doc_id)
            except Exception:
                logger.exception("drive pipeline failed: file=%s", file_id)
                await _mark_run_failed(run_id)

        await _publish_progress(user_id, "drive", "done", f"Completed — processed {processed} files", total, total)
    except Exception as exc:
        logger.exception("drive sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        await _publish_progress(user_id, "drive", "error", str(exc)[:200])
    finally:
        if error_msg:
            await _ensure_sync_state(uid, "drive", "error", error_msg)
        else:
            await _ensure_sync_state(uid, "drive", "idle")
        await _clear_progress(user_id, "drive")


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

            time_range = job.get("time_range", "1d")
            logger.info("processing %s sync job for user %s (range=%s)", source, user_id, time_range)
            if source == "gmail":
                await _process_gmail_job(user_id, token, time_range)
            elif source == "drive":
                await _process_drive_job(user_id, token, time_range)
            else:
                logger.warning("unknown source_type '%s', skipping", source)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("queue consumer iteration error")
            await asyncio.sleep(2)
