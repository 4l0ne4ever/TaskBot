from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.source_document import SourceDocument
from app.models.task import Task
from app.models.user import User
from app.services.upload_service import (
    build_s3_key,
    compute_content_hash,
    create_upload_document,
    enqueue_pipeline_job,
    ensure_supported_file,
    get_upload_status,
    new_upload_id,
    set_upload_status,
    upload_bytes_to_s3,
)

router = APIRouter()


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    filename = file.filename or ""
    try:
        ensure_supported_file(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_FILE", "message": str(exc)}) from exc

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"})

    upload_id = new_upload_id()
    content_hash = compute_content_hash(content)
    s3_key = build_s3_key(current_user.id, upload_id, filename)

    upload_bytes_to_s3(
        s3_key=s3_key,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )

    source_doc = await create_upload_document(
        db=db,
        user_id=current_user.id,
        upload_id=upload_id,
        content_hash=content_hash,
    )

    await enqueue_pipeline_job(
        {
            "user_id": str(current_user.id),
            "source_doc_id": str(source_doc.id),
            "source_type": "upload",
            "upload_id": upload_id,
            "s3_key": s3_key,
            "file_name": filename,
        }
    )
    await set_upload_status(upload_id, "queued")
    return {"upload_id": upload_id, "status": "queued"}


@router.get("/{upload_id}/status")
async def get_upload_processing_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Round 14 (2026-05-31): when status=='done', also return the count and
    IDs of tasks the pipeline extracted from this upload so the frontend can
    show a result block ("3 tasks extracted — view in Tasks →") instead of
    leaving the user staring at a green checkmark with no idea what happened.

    The agent stamps the SourceDocument with source_ref=upload_id at upload
    time and persists the tasks against that source_doc. The lookup is
    cheap: one row by source_ref + a one-shot join for the task ids.
    """
    status = await get_upload_status(upload_id)
    payload: dict = {"upload_id": upload_id, "status": status}
    if status == "done":
        stmt = select(SourceDocument).where(
            SourceDocument.user_id == current_user.id,
            SourceDocument.source_ref == upload_id,
        )
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if doc is not None:
            task_rows = (
                await db.execute(
                    select(Task.id, Task.title).where(Task.source_doc_id == doc.id)
                )
            ).all()
            payload["extracted_count"] = len(task_rows)
            payload["extracted_tasks"] = [
                {"id": str(r[0]), "title": r[1]} for r in task_rows[:10]
            ]
    return payload
