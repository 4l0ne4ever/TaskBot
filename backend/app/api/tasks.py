from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def placeholder() -> dict[str, str]:
    return {"message": "Not implemented yet"}
