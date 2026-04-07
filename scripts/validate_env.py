#!/usr/bin/env python3
"""
Load repo-root .env and verify values + optional live connectivity.
Does not print secret values (only presence, length, or redacted prefixes).

What "ERR" means here:
  - Missing/invalid values in .env (wrong format, typos) → fix .env.
  - Postgres/Redis/MCP/S3 failures often mean the *service or resource is not up yet* — not that your API keys
    in .env are wrong. Example: S3 returns 404 until you create the bucket during AWS setup.

Examples:
  ./.venv/bin/python scripts/validate_env.py              # full infra check (PG + Redis + …)
  ./.venv/bin/python scripts/validate_env.py --dev        # skip PG/Redis; soften S3/backend /health
"""
from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _fail(msg: str) -> None:
    print(f"ERR {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"WARN {msg}")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise SystemExit("python-dotenv is required: pip install python-dotenv") from exc
    if not ENV_PATH.is_file():
        raise SystemExit(f"Missing {ENV_PATH}")
    load_dotenv(ENV_PATH)


def _require(name: str) -> str:
    v = os.environ.get(name)
    if v is None or not str(v).strip():
        raise ValueError(f"Missing or empty: {name}")
    return str(v).strip()


def _check_fernet_key(raw: str) -> None:
    from cryptography.fernet import Fernet

    Fernet(raw.encode())


def _resolve_hostname(host: str) -> None:
    if host in ("localhost", "127.0.0.1", "::1"):
        return
    socket.getaddrinfo(host, None)


def _is_localhost_url(url: str) -> bool:
    try:
        p = urlparse(url)
        h = (p.hostname or "").lower()
        return h in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


def _check_backend_settings() -> None:
    cmd = [
        sys.executable,
        "-c",
        "from app.config import get_settings; get_settings(); print('backend_settings_ok')",
    ]
    r = subprocess.run(
        cmd,
        cwd=ROOT / "backend",
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "backend settings failed")


def _check_agent_settings() -> None:
    cmd = [
        sys.executable,
        "-c",
        "from app.config import get_settings; get_settings(); print('agent_settings_ok')",
    ]
    r = subprocess.run(
        cmd,
        cwd=ROOT / "agent",
        env={**os.environ, "PYTHONPATH": str(ROOT / "agent")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "agent settings failed")


async def _check_postgres(url: str) -> None:
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("asyncpg not installed") from exc
    conn = await asyncio.wait_for(asyncpg.connect(dsn=url), timeout=8)
    try:
        v = await conn.fetchval("select 1")
        if v != 1:
            raise RuntimeError("unexpected scalar")
    finally:
        await conn.close()


def _check_redis(url: str) -> None:
    import redis

    client = redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
    try:
        if client.ping() is not True:
            raise RuntimeError("ping failed")
    finally:
        client.close()


class S3BucketNotCreatedYet(Exception):
    """Bucket name/region OK for config, but AWS has no bucket yet (normal before setup)."""


def _check_s3(region: str, bucket: str) -> None:
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        msg = exc.response.get("Error", {}).get("Message", "")
        if code in ("404", "NoSuchBucket"):
            raise S3BucketNotCreatedYet(f"S3 head_bucket: {code} ({msg})") from exc
        if code == "403":
            raise RuntimeError(
                f"S3 head_bucket: {code} ({msg}). IAM needs s3:ListBucket (and correct AWS_REGION for this bucket)."
            ) from exc
        raise


def _check_groq(api_key: str, model: str) -> None:
    from groq import Groq

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8,
        temperature=0,
        messages=[{"role": "user", "content": 'Reply with JSON: {"ok":true}'}],
    )
    if not resp.choices:
        raise RuntimeError("empty Groq response")


def _check_mcp_endpoint(
    label: str,
    url: str,
    *,
    dev: bool,
) -> None:
    import httpx

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("invalid URL")
    host = parsed.hostname
    if not host:
        raise ValueError("missing host")
    try:
        _resolve_hostname(host)
    except socket.gaierror as exc:
        raise RuntimeError(
            f"hostname does not resolve ({host}). "
            f"For Google Drive there is no public drive.mcp.claude.com — set DRIVE_MCP_URL to your MCP server."
        ) from exc

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url)
    except httpx.ConnectError as exc:
        if _is_localhost_url(url):
            _warn(
                f"{label}: nothing listening at {url} — start your MCP process there "
                f"(expected until you run the Drive MCP server locally)."
            )
            return
        raise RuntimeError(f"connection failed: {exc}") from exc

    if r.status_code >= 500:
        raise RuntimeError(f"HTTP {r.status_code}")
    _ok(f"{label} URL reachable (HTTP {r.status_code})")


def _postgres_hint(exc: BaseException) -> str:
    text = str(exc).lower()
    if "connection refused" in text or "connect call failed" in text:
        return " Is Postgres running, and does host/port in DATABASE_URL match?"
    if "password authentication failed" in text:
        return " Wrong user/password in DATABASE_URL, or DB user not created yet."
    return ""


def _redis_hint(exc: BaseException) -> str:
    text = str(exc).lower()
    if "connection refused" in text or "error 61" in text:
        return " Is Redis running on the host:port in REDIS_URL?"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TaskBot .env")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Skip Postgres/Redis; S3 missing bucket + backend /health are warn-only",
    )
    args = parser.parse_args()
    dev: bool = args.dev

    _load_dotenv()
    errors = 0

    _warn(
        "Infra checks: Postgres/Redis/MCP/S3 failures usually mean services or resources are not ready yet — "
        "not necessarily wrong secrets in .env."
    )

    required_core = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "DATABASE_URL",
        "REDIS_URL",
        "GMAIL_MCP_URL",
        "DRIVE_MCP_URL",
        "CALENDAR_MCP_URL",
        "BACKEND_API_BASE_URL",
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "AWS_S3_BUCKET",
    ]
    clerk_any = bool(
        os.environ.get("CLERK_SECRET_KEY", "").strip()
        and (
            os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip()
            or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY", "").strip()
        )
    )

    for name in required_core:
        try:
            _require(name)
            _ok(f"{name} is set")
        except ValueError as exc:
            _fail(str(exc))
            errors += 1

    if clerk_any:
        _ok("Clerk keys present (NEXT_PUBLIC_ or VITE publishable + CLERK_SECRET_KEY)")
        pk = (
            os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip()
            or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY", "").strip()
        )
        sk = os.environ.get("CLERK_SECRET_KEY", "").strip()
        if pk and not pk.startswith("pk_"):
            _warn("Clerk publishable key usually starts with pk_")
        if sk and not sk.startswith("sk_"):
            _warn("Clerk secret key usually starts with sk_")
    else:
        _warn("Clerk: set CLERK_SECRET_KEY and NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY (or VITE_...)")

    try:
        jwt = _require("JWT_SECRET")
        if len(jwt) < 32:
            raise ValueError("JWT_SECRET should be at least 32 characters")
        _ok("JWT_SECRET length OK")
    except ValueError as exc:
        _fail(str(exc))
        errors += 1

    try:
        enc = _require("ENCRYPTION_KEY")
        _check_fernet_key(enc)
        _ok("ENCRYPTION_KEY is valid Fernet material")
    except Exception as exc:
        _fail(f"ENCRYPTION_KEY: {exc}")
        errors += 1

    gid = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not gid.endswith(".apps.googleusercontent.com"):
        _fail("GOOGLE_CLIENT_ID should end with .apps.googleusercontent.com")
        errors += 1
    else:
        _ok("GOOGLE_CLIENT_ID format OK")

    try:
        _check_backend_settings()
        _ok("backend app.config.Settings loads")
    except Exception as exc:
        _fail(f"backend Settings: {exc}")
        errors += 1

    try:
        _check_agent_settings()
        _ok("agent app.config.Settings loads")
    except Exception as exc:
        _fail(f"agent Settings: {exc}")
        errors += 1

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql+asyncpg://"):
        sync_url = "postgresql://" + db_url.split("postgresql+asyncpg://", 1)[1]
    else:
        sync_url = db_url

    if dev:
        _warn("Skipping PostgreSQL and Redis checks (--dev)")
    else:
        try:
            asyncio.run(_check_postgres(sync_url))
            _ok("PostgreSQL accepts connections (select 1)")
        except Exception as exc:
            _fail(f"PostgreSQL: {exc}{_postgres_hint(exc)}")
            errors += 1

        try:
            _check_redis(_require("REDIS_URL"))
            _ok("Redis PING OK")
        except Exception as exc:
            _fail(f"Redis: {exc}{_redis_hint(exc)}")
            errors += 1

    try:
        _check_s3(_require("AWS_REGION"), _require("AWS_S3_BUCKET"))
        _ok("S3 head_bucket OK")
    except S3BucketNotCreatedYet as exc:
        _warn(
            f"S3: {exc} — normal before you create bucket `{os.environ.get('AWS_S3_BUCKET', '')}` "
            f"in region `{os.environ.get('AWS_REGION', '')}`; IAM keys can still be valid."
        )
    except Exception as exc:
        if dev:
            _warn(f"S3: {exc} (--dev)")
        else:
            _fail(f"S3: {exc}")
            errors += 1

    try:
        _check_groq(_require("GROQ_API_KEY"), _require("GROQ_MODEL"))
        _ok("Groq API call OK")
    except Exception as exc:
        _fail(f"Groq: {exc}")
        errors += 1

    for label, key in (
        ("Gmail MCP", "GMAIL_MCP_URL"),
        ("Drive MCP", "DRIVE_MCP_URL"),
        ("Calendar MCP", "CALENDAR_MCP_URL"),
    ):
        try:
            url = _require(key)
            _check_mcp_endpoint(label, url, dev=dev)
        except Exception as exc:
            _fail(f"{label}: {exc}")
            errors += 1

    backend_base = os.environ.get("BACKEND_API_BASE_URL", "").rstrip("/")
    if backend_base:
        try:
            import httpx

            health = f"{backend_base}/health"
            with httpx.Client(timeout=5.0) as client:
                r = client.get(health)
            if r.status_code != 200:
                if dev:
                    _warn(f"BACKEND_API_BASE_URL /health returned {r.status_code} (API not running is OK in --dev)")
                else:
                    _warn(f"BACKEND_API_BASE_URL /health returned {r.status_code} (start API for green check)")
            else:
                _ok("BACKEND_API_BASE_URL /health OK")
        except Exception as exc:
            if dev:
                _warn(f"BACKEND_API_BASE_URL /health: {exc} (OK in --dev if API not started)")
            else:
                _warn(f"BACKEND_API_BASE_URL /health: {exc} (optional if API not running)")

    ls_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if ls_key:
        _ok("LANGSMITH_API_KEY is set (tracing configured in clients that read it)")

    print()
    if errors:
        print(f"Finished with {errors} error(s).")
        return 1
    print("All required checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
