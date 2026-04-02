from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, settings, sync, tasks, upload
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TaskBot API", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
