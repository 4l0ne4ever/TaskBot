"""Upload-job processor: fetch a previously uploaded file from S3, run the
LangGraph pipeline on it, and flip the user-visible upload status."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument

from .._runtime import get_redis, logger, settings
from ..pipeline_runner import invoke_pipeline, mark_run_failed


async def _set_upload_status(uid: str, status: str) -> None:
    # Mirrors backend/app/services/upload_service.set_upload_status — inlined
    # to avoid a cross-package import between agent and backend. Frontend
    # polls ``GET /upload/{id}/status`` which reads this same Redis key.
    # Keep the prefix in sync if you ever rename.
    r = await get_redis()
    await r.set(f"upload:status:{uid}", status)


async def process_upload_job(
    user_id: str,
    *,
    source_doc_id: str,
    s3_key: str,
    file_name: str,
    upload_id: str,
) -> None:
    """Process an uploaded file (PDF / DOCX): fetch from S3, run the pipeline,
    update the user-visible status through ``queued → extracting → done``.

    Sibling of ``process_gmail_job`` but bytes-shaped instead of message-id-
    shaped, and no OAuth token (the file is in our S3 bucket; nothing to
    authenticate against externally). This is what makes the upload path
    finally work end-to-end — before Round 12 the backend correctly staged the
    file and enqueued the job, but the queue consumer had no upload branch so
    the job sat untouched in Redis forever and the frontend polled
    ``upload:status:*`` indefinitely.

    Error handling: any failure (S3 fetch, parse, pipeline) is logged AND the
    status flips to ``"failed"`` so the UI shows something honest instead of
    an eternal spinner. The upstream ``consume_pipeline_jobs`` catch-all also
    logs unexpected exceptions, but the status is set explicitly here so the
    user-visible signal lands even on the happy pipeline-error path.
    """
    import boto3

    run_id_val: uuid.UUID | None = None
    try:
        await _set_upload_status(upload_id, "extracting")
        if not (settings.aws_s3_bucket and settings.aws_region):
            raise RuntimeError("AWS S3 not configured on agent (aws_s3_bucket / aws_region missing)")

        def _fetch() -> bytes:
            client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            obj = client.get_object(Bucket=settings.aws_s3_bucket, Key=s3_key)
            return obj["Body"].read()

        content_bytes = await asyncio.to_thread(_fetch)
        logger.info("upload pipeline: fetched %d bytes from s3 key=%s", len(content_bytes), s3_key)

        # Make sure a pipeline_run row exists so observability + dedup work
        # the same as a gmail/drive sync. The source_doc row was already
        # created by the backend at upload time (status=queued).
        run_id_val = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    PipelineRun(
                        id=run_id_val,
                        user_id=uuid.UUID(user_id),
                        source_doc_id=uuid.UUID(source_doc_id),
                        status="running",
                    )
                )

        state = {
            "user_id": user_id,
            "source_doc_id": source_doc_id,
            "pipeline_run_id": str(run_id_val),
            "source_type": "upload",
            "raw_content": content_bytes,
            "metadata": {
                "file_name": file_name,
                "upload_id": upload_id,
            },
            # No access_token: dispatch_notifications gracefully skips the
            # calendar create when access_token is missing — same fail-safe
            # already used for other no-OAuth contexts.
        }
        final_state = await invoke_pipeline(state)

        # Persist the parsed text into ``source_documents.raw_text`` so the
        # conflict UI can render the file body and ``HighlightExcerpt`` can
        # highlight ``evidence_quote`` — parity with gmail.py:278. The backend
        # creates the source_document row at upload time with raw_text=NULL
        # because text extraction (PDF/DOCX → text) only happens inside the
        # pipeline's parse_input node, so we write back here.
        cleaned_text = (final_state or {}).get("cleaned_text") or ""
        if cleaned_text:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        update(SourceDocument)
                        .where(SourceDocument.id == uuid.UUID(source_doc_id))
                        .values(raw_text=cleaned_text[:50_000])
                    )

        await _set_upload_status(upload_id, "done")
        logger.info("upload pipeline ok: upload_id=%s file=%s", upload_id, file_name)
    except Exception as exc:
        try:
            await _set_upload_status(upload_id, "failed")
        except Exception:
            pass
        await mark_run_failed(str(run_id_val) if run_id_val is not None else "", f"upload pipeline failure: {exc}")
        logger.exception("upload pipeline failed for upload_id=%s file=%s", upload_id, file_name)
        raise
