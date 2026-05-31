"""Consume sync jobs from Redis ``pipeline:jobs`` and dispatch to processors.

The heavy lifting lives in ``processors/`` and the helper modules
(``_runtime``, ``auth``, ``pressure``, ``pipeline_runner``). This file is the
top-level BLPOP loop and the per-source-type dispatch table.

Test back-compat: a few internals (``_find_existing_source_doc``,
``_extract_drive_raw_content``) are re-exported here so existing
``from app.scheduler.queue_consumer import …`` lines in
``agent/tests/unit/test_queue_consumer_*.py`` keep working.
"""

from __future__ import annotations

import asyncio
import json

from ._runtime import get_redis, logger, settings
from .pipeline_runner import find_existing_source_doc as _find_existing_source_doc
from .processors.calendar_resync import process_calendar_resync_job
from .processors.daily_digest import process_daily_digest_job
from .processors.drive import extract_drive_raw_content as _extract_drive_raw_content
from .processors.drive import process_drive_job
from .processors.gmail import process_gmail_job
from .processors.upload import process_upload_job
from .processors.weekly_brief import process_weekly_brief_job

__all__ = [
    "consume_pipeline_jobs",
    "_find_existing_source_doc",
    "_extract_drive_raw_content",
]


async def consume_pipeline_jobs() -> None:
    """BLPOP loop: pick jobs from ``pipeline:jobs`` and dispatch."""
    r = await get_redis()
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
            # Upload jobs carry no OAuth token (the file lives in our S3 bucket,
            # no external service to authenticate against). Dispatch them BEFORE
            # the token-required guard below — pre-Round-12 they fell through
            # that guard and the upload UI showed an eternal spinner. See §7.14
            # in tests/e2e/real-world-validation.md for the forensic.
            if source == "upload":
                if not user_id:
                    logger.warning("upload job missing user_id, skipping: %s", raw[:200])
                    continue
                source_doc_id = job.get("source_doc_id", "")
                s3_key = job.get("s3_key", "")
                file_name = job.get("file_name", "")
                upload_id = job.get("upload_id", "")
                if not (source_doc_id and s3_key and upload_id):
                    logger.warning("upload job missing required field(s), skipping: %s", raw[:200])
                    continue
                logger.info("processing upload job for user %s upload=%s", user_id, upload_id)
                await process_upload_job(
                    user_id,
                    source_doc_id=source_doc_id,
                    s3_key=s3_key,
                    file_name=file_name,
                    upload_id=upload_id,
                )
                continue
            if not user_id or not token:
                logger.warning("invalid job payload, skipping: %s", raw[:200])
                continue

            if source == "calendar_resync":
                task_id = job.get("task_id", "")
                if not task_id:
                    logger.warning("calendar_resync job missing task_id, skipping")
                    continue
                logger.info("processing calendar_resync job for user %s task %s", user_id, task_id)
                await process_calendar_resync_job(user_id, token, task_id)
                continue

            if source == "weekly_brief":
                logger.info("processing weekly_brief job for user %s", user_id)
                await process_weekly_brief_job(user_id, token)
                continue

            if source == "daily_digest":
                logger.info("processing daily_digest job for user %s", user_id)
                await process_daily_digest_job(user_id, token)
                continue

            time_range = job.get("time_range", "1d")
            sync_profile = job.get("sync_profile", "balanced")
            # Round 11: folder defaults to "inbox" so pre-Round-11 queued jobs
            # (which don't carry the field) still pick the correct query.
            folder = job.get("folder", "inbox") if source == "gmail" else "inbox"
            logger.info(
                "processing %s sync job for user %s (range=%s, profile=%s, folder=%s)",
                source,
                user_id,
                time_range,
                sync_profile,
                folder,
            )
            if source == "gmail":
                await process_gmail_job(user_id, token, time_range, sync_profile, raw_job=job, folder=folder)
            elif source == "drive":
                await process_drive_job(user_id, token, time_range, sync_profile, raw_job=job)
            else:
                logger.warning("unknown source_type '%s', skipping", source)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("queue consumer iteration error")
            await asyncio.sleep(2)
