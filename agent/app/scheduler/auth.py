"""MCP auth-revoke detection + streak tracking.

A Google OAuth token can be revoked (user un-consents) and that surfaces as a
401 from the Gmail/Drive MCP. Retry can't fix it — only re-consent can — so
we count consecutive 401s per (user, source) and after a threshold mark the
sync as ``disabled`` until reconnect, with a distinct ``mcp_auth_revoked``
pipeline error so the dashboard can render a reconnect banner.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.services.observability import record_pipeline_error

from ._runtime import get_redis, settings


def is_auth_revoked_error(error_text: str) -> bool:
    """True if the MCP/HTTP error text looks like user-level token revocation
    (HTTP 401, ``invalid_grant``, ``Invalid Credentials``, …).

    User-actionable — the fix is "reconnect your Google account", not "retry
    later". Treated separately from transient MCP 5xx/network errors so the
    scheduler can break the futile 15-minute retry loop and surface a clear
    reconnect signal (Google OAuth docs: revoked access tokens keep returning
    401 until re-consent; RFC 6819 §5.2.2.2 recommends graceful degradation).
    """
    if not error_text:
        return False
    t = error_text.lower()
    if "mcp call failed [401]" in t or "http 401" in t or " 401:" in t or "status: 401" in t:
        return True
    return (
        "invalid_grant" in t
        or "invalid credentials" in t
        or "token expired" in t
        or "token revoked" in t
    )


async def is_sync_disabled_for_auth(user_id: str, source_type: str) -> dict | None:
    """Return the disable-record if auto-sync is suspended for this user's
    (source_type) because of a prior 401 streak, else ``None``."""
    r = await get_redis()
    raw = await r.get(f"sync:disabled:{user_id}:{source_type}")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


async def record_mcp_auth_outcome(
    user_id: str,
    source_type: str,
    *,
    auth_error: bool,
) -> tuple[int, bool]:
    """Track consecutive MCP 401 outcomes per (user, source) and return
    ``(streak_after, should_disable_sync)``.

    Design:
    - Each sync attempt either authenticates (``auth_error=False`` → clear
      streak) or fails with an auth-class error (``auth_error=True`` →
      increment streak).
    - When the streak reaches ``settings.mcp_auth_revoke_streak_threshold``,
      the caller should (a) emit a distinct ``source_type="mcp_auth_revoked"``
      pipeline error so dashboards/UI can prompt reconnection, and (b) write
      a time-bounded flag that ``_get_sync_eligible_users`` honors to skip
      the user until re-auth.
    - Per-(user, source) keys: Google can revoke one scope without the other
      (rare but observed).
    - TTL on the streak key keeps an abandoned account from accumulating
      forever — after a quiet day the counter resets.
    """
    r = await get_redis()
    streak_key = f"mcp:auth_streak:{user_id}:{source_type}"
    if not auth_error:
        await r.delete(streak_key)
        return 0, False
    new_val = await r.incr(streak_key)
    await r.expire(streak_key, max(settings.mcp_auth_revoke_disable_ttl_seconds, 3600))
    threshold = max(settings.mcp_auth_revoke_streak_threshold, 1)
    should_disable = int(new_val) >= threshold
    if should_disable:
        disable_key = f"sync:disabled:{user_id}:{source_type}"
        await r.set(
            disable_key,
            json.dumps(
                {
                    "reason": "mcp_auth_revoked",
                    "since": datetime.now(UTC).isoformat(),
                    "streak": int(new_val),
                    "source_type": source_type,
                }
            ),
            ex=max(settings.mcp_auth_revoke_disable_ttl_seconds, 3600),
        )
    return int(new_val), should_disable


async def flag_user_auth_revoked(user_id: str, source_type: str, error_text: str) -> None:
    """Increment the 401 streak and, if over threshold, emit a distinct
    ``mcp_auth_revoked`` pipeline error so operators (or the frontend) can
    prompt the user to reconnect. Writing the ``sync:disabled:*`` key happens
    inside :func:`record_mcp_auth_outcome`.

    The distinct source_type matters: ``"gmail"``/``"drive"`` 401s were
    historically swallowed as generic sync errors; surfacing them as
    ``"mcp_auth_revoked"`` makes the dashboard counter and the user-visible
    "reconnect Google" banner straightforward without adding a new enum.
    """
    streak, disabled = await record_mcp_auth_outcome(user_id, source_type, auth_error=True)
    if disabled:
        record_pipeline_error(
            source_type="mcp_auth_revoked",
            user_id=user_id,
            error=(
                f"{source_type}: auth 401 streak={streak} "
                f">= threshold={settings.mcp_auth_revoke_streak_threshold}; "
                f"auto-sync suspended for {source_type} until reconnect. "
                f"last_error={error_text[:160]}"
            ),
        )
