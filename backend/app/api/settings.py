from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter()


def _sync_config(user: User) -> dict:
    config = user.sync_config or {}
    defaults = get_settings()
    return {
        "gmail_interval": config.get("gmail_interval", defaults.sync_gmail_interval_minutes),
        "drive_interval": config.get("drive_interval", defaults.sync_drive_interval_minutes),
    }


@router.get("", response_model=SettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
) -> dict:
    cfg = _sync_config(current_user)
    return {
        **cfg,
        "google_connected": current_user.oauth_token is not None,
    }


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    config = dict(user.sync_config or {})
    changes = body.model_dump(exclude_unset=True)
    config.update(changes)
    user.sync_config = config

    return {
        **_sync_config(user),
        "google_connected": user.oauth_token is not None,
    }


@router.post("/disconnect")
async def disconnect_google(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.oauth_token:
        return {"message": "Already disconnected"}

    user.oauth_token = None
    return {"message": "Google account disconnected"}
