from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update as _update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conflict import Conflict
from app.models.user import User
from app.schemas.conflict import ConflictResponse, ConflictResolve

router = APIRouter()


@router.get("", response_model=list[ConflictResponse])
async def list_conflicts(
    resolved: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Conflict]:
    stmt = select(Conflict).where(Conflict.user_id == current_user.id)
    if resolved is not None:
        stmt = stmt.where(Conflict.resolved == resolved)
    stmt = stmt.order_by(Conflict.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/dismiss-all")
async def dismiss_all_conflicts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    stmt = (
        _update(Conflict)
        .where(Conflict.user_id == current_user.id, Conflict.resolved == False)  # noqa: E712
        .values(resolved=True, description="[resolved:dismiss_all]")
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"dismissed": result.rowcount}


@router.patch("/{conflict_id}", response_model=ConflictResponse)
async def resolve_conflict(
    conflict_id: UUID,
    body: ConflictResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conflict:
    stmt = select(Conflict).where(Conflict.id == conflict_id, Conflict.user_id == current_user.id)
    result = await db.execute(stmt)
    conflict = result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(
            status_code=404, detail={"code": "CONFLICT_NOT_FOUND", "message": "Conflict not found"}
        )
    if conflict.resolved:
        raise HTTPException(
            status_code=409, detail={"code": "ALREADY_RESOLVED", "message": "Conflict already resolved"}
        )

    conflict.resolved = True
    conflict.description = f"[resolved:{body.resolution}] {conflict.description or ''}"
    return conflict
