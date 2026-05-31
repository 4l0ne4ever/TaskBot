from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, calendar, conflicts, digest, observability, settings as settings_router, sync, tasks, upload
from app.config import get_settings
from app.db.session import init_db
from app.middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TaskBot API", lifespan=lifespan)


def _cors_origins() -> list[str]:
    """Derive the CORS allow-list from ``settings.frontend_url``.

    Browsers treat ``localhost`` and ``127.0.0.1`` as distinct origins, so we
    auto-mirror the host name when one form is configured to spare developers
    a confusing CORS rejection. Production deployments override
    ``FRONTEND_URL`` to the public domain and only that gets allowed.
    """
    base = get_settings().frontend_url.rstrip("/")
    mirrors = {base}
    if "localhost" in base:
        mirrors.add(base.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in base:
        mirrors.add(base.replace("127.0.0.1", "localhost"))
    return sorted(mirrors)


app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(conflicts.router, prefix="/tasks/conflicts", tags=["conflicts"])
app.include_router(observability.router, prefix="/observability", tags=["observability"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(digest.router, prefix="/digest", tags=["digest"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
