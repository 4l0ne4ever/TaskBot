"""Drive job processor — fetch files, dedup, run LangGraph pipeline."""

from __future__ import annotations

import asyncio
import base64
import uuid

from app.db.session import AsyncSessionLocal
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.services.observability import record_pipeline_error
from app.services.sync_service import (
    _drive_limit_for_profile,
    pull_recent_drive_files,
)

from .._runtime import (
    clear_progress,
    ensure_sync_state,
    logger,
    publish_progress,
    settings,
)
from ..auth import (
    flag_user_auth_revoked,
    is_auth_revoked_error,
    is_sync_disabled_for_auth,
    record_mcp_auth_outcome,
)
from ..pipeline_runner import (
    content_hash,
    find_existing_source_doc,
    invoke_pipeline,
    mark_run_failed,
    time_range_to_datetime,
)
from ..pressure import llm_pressure_snapshot, requeue_deferred_job

_FETCH_CONCURRENCY = 5


def extract_drive_raw_content(content: str | bytes | dict | None) -> str | bytes | None:
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


async def process_drive_job(
    user_id: str,
    access_token: str,
    time_range: str = "1d",
    sync_profile: str = "balanced",
    raw_job: dict | None = None,
) -> None:
    uid = uuid.UUID(user_id)
    profile_limit = _drive_limit_for_profile(sync_profile)
    disabled = await is_sync_disabled_for_auth(user_id, "drive")
    if disabled and str(disabled.get("reason")) == "mcp_auth_revoked":
        logger.info(
            "drive sync: skipping user %s — auth_revoked since %s",
            user_id,
            disabled.get("since"),
        )
        await ensure_sync_state(
            uid,
            "drive",
            "error",
            f"mcp_auth_revoked: reconnect Google account (since {disabled.get('since')})",
        )
        await publish_progress(
            user_id,
            "drive",
            "error",
            "Google authorization was revoked — reconnect in Settings to resume sync",
        )
        return
    await ensure_sync_state(uid, "drive", "running")
    await publish_progress(
        user_id,
        "drive",
        "connecting",
        f"Connecting to Google Drive (last {time_range}, profile={sync_profile}, cap={profile_limit})",
    )

    last_sync_at = time_range_to_datetime(time_range)
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
            await publish_progress(user_id, "drive", "done", "No new files found")
            return

        total = len(files)
        await publish_progress(user_id, "drive", "fetching", f"Fetching {total} files", 0, total)

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
        await publish_progress(user_id, "drive", "processing", f"Processing {total} files", 0, total)

        processed = 0
        skipped_dedup = 0
        failed_docs = 0
        (
            llm_pressure_high,
            pressure_ratio,
            pressure_sample_size,
            daily_quota_exhausted,
        ) = await llm_pressure_snapshot()
        max_docs_under_pressure = max(settings.llm_pressure_max_documents_per_job, 1)
        deferred = 0
        if daily_quota_exhausted:
            error_msg = (
                f"llm_daily_quota_exhausted: {pressure_ratio:.0%} rate-limited "
                f"(TPD/RPD) in last {pressure_sample_size} calls; sync will "
                f"retry after the next UTC day boundary"
            )
            logger.warning("drive sync: %s (user=%s)", error_msg, user_id)
            await publish_progress(user_id, "drive", "throttling", error_msg, 0, total)
            return
        if llm_pressure_high:
            await publish_progress(
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
            raw = extract_drive_raw_content(content)
            if raw is None:
                continue
            if llm_pressure_high and processed >= max_docs_under_pressure:
                deferred += 1
                continue

            chash = content_hash(raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace"))

            doc_id_val: uuid.UUID | None = None
            run_id_val: uuid.UUID | None = None
            skip_pipeline = False
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    existing = await find_existing_source_doc(
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
            await publish_progress(user_id, "drive", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                "content_hash": chash, "source_type": "drive", "raw_content": raw,
                "metadata": {"file_name": file_name, "sync_profile": sync_profile, "dedupe_group_id": file_id},
            }
            try:
                await invoke_pipeline(state)
                logger.info("drive pipeline ok: file=%s doc=%s", file_id, doc_id)
            except Exception as exc:
                logger.exception("drive pipeline failed: file=%s", file_id)
                failed_docs += 1
                await mark_run_failed(run_id, error_msg=str(exc)[:500])
                record_pipeline_error(
                    source_type="drive",
                    user_id=user_id,
                    error=f"doc={doc_id}: {str(exc)[:400]}",
                )
                err = str(exc).lower()
                if "429" in err or "rate limit" in err or "rate_limit" in err:
                    remaining = max(total - (idx + 1), 0)
                    deferred += remaining
                    await publish_progress(
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
                asyncio.create_task(requeue_deferred_job(raw_job, deferred))
        if failed_docs and error_msg is None:
            error_msg = f"partial_failure: {failed_docs}/{total} documents failed"
        await publish_progress(user_id, "drive", "done", detail, processed, total)
    except Exception as exc:
        logger.exception("drive sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        auth_error = is_auth_revoked_error(error_msg)
        record_pipeline_error(source_type="drive", user_id=user_id, error=error_msg)
        if auth_error:
            await flag_user_auth_revoked(user_id, "drive", error_msg)
        await publish_progress(user_id, "drive", "error", str(exc)[:200])
    else:
        await record_mcp_auth_outcome(user_id, "drive", auth_error=False)
    finally:
        if error_msg:
            await ensure_sync_state(uid, "drive", "error", error_msg)
        else:
            await ensure_sync_state(uid, "drive", "idle")
        await clear_progress(user_id, "drive")
