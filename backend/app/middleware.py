from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

RATE_LIMIT = 60
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by JWT sub (or remote IP for unauthenticated)."""

    def __init__(self, app, limit: int = RATE_LIMIT, window: int = WINDOW_SECONDS):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _key(self, request: Request) -> str:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
            parts = token.split(".")
            if len(parts) == 3:
                import base64, json
                try:
                    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(padded))
                    sub = payload.get("sub")
                    if sub:
                        return f"user:{sub}"
                except Exception:
                    pass
        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        key = self._key(request)
        now = time.monotonic()
        bucket = self._buckets[key]
        cutoff = now - self.window
        self._buckets[key] = [t for t in bucket if t > cutoff]

        if len(self._buckets[key]) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": {"code": "RATE_LIMITED", "message": "Too many requests"}},
            )
        self._buckets[key].append(now)
        return await call_next(request)
