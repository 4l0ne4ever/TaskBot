"""Weekly Brief manual trigger (Phase 8.3).

The scheduled send lives in the agent (APScheduler cron). This endpoint is the
on-demand path — what a manager (and a thesis demo) actually clicks. It mirrors
the conflict-merge calendar enqueue: decrypt + refresh the Google token, then
push a ``weekly_brief`` job onto the pipeline queue for the agent to build and
self-send via the Gmail MCP. Requires the gmail.send scope on the grant.
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


@router.post("/send")
async def send_weekly_brief(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    # Reuse the calendar-resync token dance: decrypts, refreshes, and persists
    # the rotated token on current_user (committed below).
    from app.api.conflicts import _build_calendar_resync_payload

    access_token, info = await _build_calendar_resync_payload(current_user)
    await db.commit()  # persist any refreshed token before enqueue

    if not access_token:
        return {
            "status": "skipped",
            "reason": info.reason,
            "message": "Reconnect Google (with send permission) to email your brief.",
        }

    settings = get_settings()
    redis_client = await get_redis()
    await redis_client.rpush(
        settings.pipeline_queue_name,
        json.dumps(
            {
                "user_id": str(current_user.id),
                "source_type": "weekly_brief",
                "access_token": access_token,
                "triggered_by": "manual",
            }
        ),
    )
    return {"status": "queued", "message": "Weekly brief is sending in the background."}
