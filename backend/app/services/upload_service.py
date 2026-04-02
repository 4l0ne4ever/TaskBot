import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import boto3
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.redis import get_redis
from app.models.source_document import SourceDocument

settings = get_settings()


def compute_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_s3_key(user_id: UUID, upload_id: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    return f"{user_id}/{upload_id}.{ext}"


def ensure_supported_file(filename: str) -> None:
    lower = filename.lower()
    if not (lower.endswith(".pdf") or lower.endswith(".docx")):
        raise ValueError("Only PDF and DOCX are supported")


async def enqueue_pipeline_job(payload: dict) -> None:
    redis_client = await get_redis()
    await redis_client.rpush(settings.pipeline_queue_name, json.dumps(payload))


async def set_upload_status(upload_id: str, status: str) -> None:
    redis_client = await get_redis()
    await redis_client.set(f"upload:status:{upload_id}", status)


async def get_upload_status(upload_id: str) -> str:
    redis_client = await get_redis()
    value = await redis_client.get(f"upload:status:{upload_id}")
    return value or "unknown"


async def create_upload_document(
    *,
    db: AsyncSession,
    user_id: UUID,
    upload_id: str,
    content_hash: str,
) -> SourceDocument:
    doc = SourceDocument(
        user_id=user_id,
        source_type="upload",
        source_ref=upload_id,
        content_hash=content_hash,
        raw_text=None,
        processed_at=datetime.now(UTC),
    )
    db.add(doc)
    await db.flush()
    return doc


def upload_bytes_to_s3(*, s3_key: str, content: bytes, content_type: str) -> None:
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    s3_client.put_object(Bucket=settings.aws_s3_bucket, Key=s3_key, Body=content, ContentType=content_type)


def new_upload_id() -> str:
    return str(uuid4())
