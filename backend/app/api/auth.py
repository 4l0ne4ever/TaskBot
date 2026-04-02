from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.config import get_settings
from app.services.auth_service import (
    build_google_auth_url,
    create_jwt,
    encrypt_token,
    exchange_code_for_tokens,
)

router = APIRouter()
settings = get_settings()

@router.get("/google")
async def auth_google() -> RedirectResponse:
    return RedirectResponse(url=build_google_auth_url())


@router.get("/callback")
async def auth_callback(
    code: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    oauth_data = await exchange_code_for_tokens(code)
    tokens = oauth_data["tokens"]
    userinfo = oauth_data["userinfo"]
    email = userinfo.get("email")
    google_id = userinfo.get("id")
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return email")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    encrypted = encrypt_token(tokens)

    if user is None:
        user = User(
            id=uuid4(),
            email=email,
            google_id=google_id,
            oauth_token=encrypted,
            sync_config={
                "gmail_interval": settings.sync_gmail_interval_minutes,
                "drive_interval": settings.sync_drive_interval_minutes,
            },
            last_active_at=datetime.now(UTC),
        )
        db.add(user)
    else:
        user.google_id = google_id
        user.oauth_token = encrypted
        user.last_active_at = datetime.now(UTC)

    token = create_jwt(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def auth_me(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"id": str(current_user.id), "email": current_user.email}


@router.post("/logout")
async def auth_logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.oauth_token = None
    return {"message": "Logged out"}
