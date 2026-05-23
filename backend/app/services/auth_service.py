import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    # gmail.send lets the Weekly Brief (Phase 8.3) send the manager their own
    # digest. Adding a scope invalidates existing grants — users must logout +
    # re-consent once before send works.
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.strip()
    return Fernet(key.encode())


def encrypt_token(token_dict: dict) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(token_dict).encode()).decode()


def decrypt_token(encrypted: str) -> dict:
    fernet = _get_fernet()
    return json.loads(fernet.decrypt(encrypted.encode()))


def create_jwt(user_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(days=7),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def build_google_auth_url() -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": secrets.token_urlsafe(24),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    settings = get_settings()
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
        token_resp.raise_for_status()
        tokens = token_resp.json()

        access_token = tokens.get("access_token")
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

    return {"tokens": tokens, "userinfo": userinfo}


async def refresh_google_access_token(refresh_token: str) -> tuple[dict | None, str | None]:
    settings = get_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
    except Exception as exc:
        return None, f"transport:{type(exc).__name__}"
    if resp.status_code >= 400:
        body = ""
        try:
            body = (resp.text or "")[:160]
        except Exception:
            body = ""
        return None, f"http_{resp.status_code}:{body}".strip()
    try:
        data = resp.json()
    except Exception:
        return None, "invalid_response:json"
    if not isinstance(data, dict) or not data.get("access_token"):
        return None, "invalid_response:no_access_token"
    return data, None


def merge_refreshed_tokens(existing_tokens: dict, refreshed_tokens: dict) -> dict:
    merged = dict(existing_tokens)
    for key in ("access_token", "refresh_token", "expires_in", "scope", "token_type"):
        if refreshed_tokens.get(key) is not None:
            merged[key] = refreshed_tokens[key]
    return merged
