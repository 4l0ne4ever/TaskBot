from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, calendar, conflicts, observability, settings, sync, tasks, upload
from app.db.session import init_db
from app.middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TaskBot API", lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(conflicts.router, prefix="/tasks/conflicts", tags=["conflicts"])
app.include_router(observability.router, prefix="/observability", tags=["observability"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
