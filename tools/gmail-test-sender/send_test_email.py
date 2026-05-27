#!/usr/bin/env python3
"""
Send test Gmail from account A → inbox B for TaskBot sync testing.

Standalone — does not import TaskBot agent/backend. Uses Gmail API + OAuth
for the sender account only.

Setup (once):
  Reuses TaskBot Web OAuth client from repo .env (GOOGLE_CLIENT_ID/SECRET).
  Auth uses GOOGLE_REDIRECT_URI (same as TaskBot login — already in GCP).
  Before --auth, free port 8000:  docker compose stop backend
  Then:
  1. cp .env.example .env — set GMAIL_TEST_SENDER and GMAIL_TEST_RECIPIENT.
  2. python -m venv .venv && .venv/bin/pip install -r requirements.txt
  3. .venv/bin/python send_test_email.py --auth
  4. docker compose start backend

Send:
  .venv/bin/python send_test_email.py --list-fixtures
  .venv/bin/python send_test_email.py --fixture hc01_proposal_draft
  .venv/bin/python send_test_email.py --category high_confidence --dry-run
  .venv/bin/python send_test_email.py --batch --delay 4

Fixtures: fixtures/manifest.json (20 mails: 10 high_confidence, 10 normal).
Recipient must be the Gmail account connected in TaskBot (currently emilywithherpet@gmail.com).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
import webbrowser
from datetime import UTC, datetime
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# Python may hang on broken IPv6 routes; prefer IPv4 for Google API calls.
_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4_first(
    host: str,
    port: int | str | None,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
):
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    v4 = [r for r in results if r[0] == socket.AF_INET]
    v6 = [r for r in results if r[0] == socket.AF_INET6]
    return v4 + v6


socket.getaddrinfo = _getaddrinfo_ipv4_first

from dotenv import load_dotenv
import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent
REPO_ENV = ROOT.parents[1] / ".env"
FIXTURES = ROOT / "fixtures"
MANIFEST = FIXTURES / "manifest.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SUBJECT_PREFIX = "[TaskBot test]"


def _load_env() -> None:
    load_dotenv(REPO_ENV, override=False)
    load_dotenv(ROOT / ".env", override=False)
    # Required for http://localhost redirect during local OAuth.
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _oauth_port() -> int:
    return int(os.getenv("GMAIL_TEST_OAUTH_PORT", "8765"))


def _oauth_host() -> str:
    return os.getenv("GMAIL_TEST_OAUTH_HOST", "localhost").strip() or "localhost"


def _oauth_redirect_uri(port: int | None = None, host: str | None = None) -> str:
    p = port if port is not None else _oauth_port()
    h = host if host is not None else _oauth_host()
    return f"http://{h}:{p}/"


def _resolve_redirect_uri(cfg: dict | None) -> str:
    """Pick redirect URI — Web clients reuse TaskBot callback (already registered)."""
    explicit = os.getenv("GMAIL_TEST_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    if cfg and "web" in cfg:
        taskbot = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
        if taskbot:
            return taskbot
    return _oauth_redirect_uri()


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _run_local_server_with_redirect(
    flow: InstalledAppFlow,
    redirect_uri: str,
    *,
    open_browser: bool = True,
) -> None:
    """Local OAuth callback server that supports paths (e.g. /auth/callback)."""
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    expected_path = parsed.path or "/"

    if _port_in_use(host, port):
        print(
            f"\nPort {port} is in use on {host}. "
            f"Stop whatever binds it before --auth.\n"
            "TaskBot backend uses port 8000 — run from repo root:\n"
            "  docker compose stop backend\n",
            file=sys.stderr,
        )
        sys.exit(1)

    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    captured: dict[str, str | None] = {"uri": None}

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:
            return

        def do_GET(self) -> None:
            req_path = urlparse(self.path).path
            if req_path != expected_path:
                self.send_error(404)
                return
            captured["uri"] = f"http://{host}:{port}{self.path}"
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OAuth OK. Return to the terminal.")

    flow.redirect_uri = redirect_uri
    print(f"Listening for OAuth callback on {redirect_uri}")

    if open_browser:
        webbrowser.open(auth_url, new=1, autoraise=True)
    else:
        print(f"\nOpen this URL in your browser:\n{auth_url}\n")

    server = HTTPServer((host, port), _Handler)
    try:
        server.handle_request()
    finally:
        server.server_close()

    if not captured["uri"]:
        print("No OAuth callback received.", file=sys.stderr)
        sys.exit(1)

    # oauthlib expects https in authorization_response (google_auth_oauthlib convention).
    flow.fetch_token(authorization_response=captured["uri"].replace("http", "https", 1))


def _client_config_from_env() -> dict | None:
    """Build OAuth client JSON from TaskBot's GOOGLE_CLIENT_ID/SECRET in repo .env."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    redirect = _resolve_redirect_uri({"web": {}})
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect],
        }
    }


def _load_client_config(creds_path: Path) -> dict | None:
    if creds_path.exists():
        return json.loads(creds_path.read_text(encoding="utf-8"))
    return _client_config_from_env()


def _client_id_from_config(cfg: dict) -> str:
    if "installed" in cfg:
        return str(cfg["installed"].get("client_id", ""))
    if "web" in cfg:
        return str(cfg["web"].get("client_id", ""))
    return ""


def _oauth_flow(creds_path: Path, redirect: str) -> InstalledAppFlow:
    cfg = _load_client_config(creds_path)
    if cfg is None:
        print(
            "No OAuth credentials found. Set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in "
            f"{REPO_ENV} (same Web client as TaskBot).",
            file=sys.stderr,
        )
        sys.exit(1)

    if "installed" in cfg:
        flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    elif "web" in cfg:
        flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    else:
        print("credentials.json must contain 'installed' or 'web'.", file=sys.stderr)
        sys.exit(1)

    flow.redirect_uri = redirect
    return flow


def _print_oauth_debug(creds_path: Path) -> None:
    cfg = _load_client_config(creds_path)
    if cfg is None:
        print("No OAuth credentials — see --auth setup.", file=sys.stderr)
        sys.exit(1)

    redirect = _resolve_redirect_uri(cfg)
    client_id = _client_id_from_config(cfg)
    client_kind = "Desktop (installed)" if "installed" in cfg else "Web"
    flow = _oauth_flow(creds_path, redirect)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    qs = parse_qs(urlparse(auth_url).query)

    print(f"Client type: {client_kind}")
    print(f"client_id:   {client_id}")
    print(f"redirect_uri sent to Google: {unquote(qs.get('redirect_uri', ['?'])[0])}")
    print()
    if "web" in cfg and redirect == os.getenv("GOOGLE_REDIRECT_URI", "").strip():
        print("Using TaskBot redirect URI (already in GCP — no :8765 URI needed).")
        print("Before --auth: docker compose stop backend  (frees port 8000)")
    elif "web" in cfg:
        print("Web client — this redirect URI must be in GCP Authorized redirect URIs.")
    print()
    print("Auth URL (open in incognito if retrying):")
    print(auth_url)


def _run_oauth_flow(creds_path: Path, *, open_browser: bool = True) -> Credentials:
    cfg = _load_client_config(creds_path)
    if cfg is None:
        print("No OAuth credentials found.", file=sys.stderr)
        sys.exit(1)

    redirect = _resolve_redirect_uri(cfg)
    client_id = _client_id_from_config(cfg)
    client_kind = "Desktop" if "installed" in cfg else "Web"
    print(f"OAuth client ({client_kind}): {client_id[:24]}…")
    print(f"OAuth redirect URI: {redirect}")

    flow = _oauth_flow(creds_path, redirect)

    if "installed" in cfg:
        parsed = urlparse(redirect)
        return flow.run_local_server(
            host=parsed.hostname or "localhost",
            port=parsed.port or _oauth_port(),
            redirect_uri_trailing_slash=redirect.endswith("/"),
            open_browser=open_browser,
        )

    _run_local_server_with_redirect(flow, redirect, open_browser=open_browser)
    return flow.credentials


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Missing {name} in {ROOT / '.env'} (see .env.example)", file=sys.stderr)
        sys.exit(1)
    return value


def _paths() -> tuple[Path, Path]:
    creds = Path(os.getenv("GMAIL_TEST_CREDENTIALS", "credentials.json"))
    token = Path(os.getenv("GMAIL_TEST_TOKEN", "token.json"))
    if not creds.is_absolute():
        creds = ROOT / creds
    if not token.is_absolute():
        token = ROOT / token
    return creds, token


def get_gmail_service(*, force_auth: bool = False):
    _load_env()
    creds_path, token_path = _paths()
    creds: Credentials | None = None

    if not force_auth and token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if force_auth:
        creds = _run_oauth_flow(creds_path)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"Saved token → {token_path}")
    elif creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as exc:
            print(
                f"Token refresh failed ({exc}). Re-run OAuth:\n"
                "  docker compose stop backend\n"
                "  .venv/bin/python send_test_email.py --auth\n"
                "  docker compose start backend",
                file=sys.stderr,
            )
            sys.exit(1)
    elif creds and creds.valid:
        token_path.write_text(creds.to_json(), encoding="utf-8")
    else:
        print(
            "No valid token. Run OAuth once (backend must release port 8000):\n"
            "  docker compose stop backend\n"
            "  .venv/bin/python send_test_email.py --auth\n"
            "  docker compose start backend",
            file=sys.stderr,
        )
        sys.exit(1)

    return build(
        "gmail",
        "v1",
        http=AuthorizedHttp(creds, http=httplib2.Http(timeout=30)),
        cache_discovery=False,
    )


def _build_raw_message(*, sender: str, to: str, subject: str, body: str) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return raw


def _load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _fixture_names(*, category: str | None = None) -> list[str]:
    data = _load_manifest()
    names = sorted(data.keys())
    if category:
        names = [n for n in names if data[n].get("category") == category]
    return names


def _list_fixtures(*, category: str | None = None) -> None:
    data = _load_manifest()
    if not data:
        print("No fixtures in fixtures/manifest.json")
        return
    names = _fixture_names(category=category)
    if not names:
        print(f"No fixtures for category={category!r}")
        return
    current_cat = ""
    for name in names:
        meta = data[name]
        cat = str(meta.get("category") or "?")
        if cat != current_cat:
            print(f"\n[{cat}] ({sum(1 for n in names if data[n].get('category') == cat)} mails)")
            current_cat = cat
        subj = meta.get("subject", "")
        notes = meta.get("notes", "")
        print(f"  {name:28}  {subj}")
        if notes:
            print(f"    ↳ {notes}")


def _resolve_fixture(name: str) -> tuple[str, str]:
    data = _load_manifest()
    if name not in data:
        known = ", ".join(sorted(data)) or "(none)"
        print(f"Unknown fixture {name!r}. Known: {known}", file=sys.stderr)
        sys.exit(1)
    meta = data[name]
    body_file = meta.get("body_file")
    if not isinstance(body_file, str):
        print(f"Fixture {name} missing body_file in manifest", file=sys.stderr)
        sys.exit(1)
    path = FIXTURES / body_file
    if not path.exists():
        print(f"Missing body file: {path}", file=sys.stderr)
        sys.exit(1)
    subject = str(meta.get("subject") or name)
    if not subject.startswith(SUBJECT_PREFIX):
        subject = f"{SUBJECT_PREFIX} {subject}"
    body = path.read_text(encoding="utf-8")
    return subject, body


def _send_one(
    service,
    *,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    fixture_name: str | None,
    unique_subject: bool,
    batch_stamp: str | None,
) -> str:
    if unique_subject:
        parts = [subject]
        if batch_stamp:
            parts.append(f"[{batch_stamp}]")
        if fixture_name:
            parts.append(f"[{fixture_name}]")
        else:
            parts.append(f"[{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}]")
        subject = " ".join(parts)

    raw = _build_raw_message(sender=sender, to=recipient, subject=subject, body=body)
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return str(result.get("id", "?"))


def send_email(
    *,
    subject: str,
    body: str,
    fixture_name: str | None = None,
    unique_subject: bool = True,
    batch_stamp: str | None = None,
    dry_run: bool = False,
) -> None:
    _load_env()
    sender = _require_env("GMAIL_TEST_SENDER")
    recipient = _require_env("GMAIL_TEST_RECIPIENT")

    display_subject = subject
    if unique_subject:
        if batch_stamp:
            display_subject = f"{subject} [{batch_stamp}]"
        if fixture_name:
            display_subject = f"{display_subject} [{fixture_name}]"
        elif unique_subject and not batch_stamp:
            display_subject = f"{subject} [{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}]"

    print(f"From:    {sender}")
    print(f"To:      {recipient}")
    print(f"Subject: {display_subject}")
    print(f"Body:    {len(body)} chars")
    if dry_run:
        print("\n(dry-run — not sent)")
        print("---")
        print(body[:600] + ("…" if len(body) > 600 else ""))
        return

    service = get_gmail_service()
    try:
        msg_id = _send_one(
            service,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            fixture_name=fixture_name,
            unique_subject=unique_subject,
            batch_stamp=batch_stamp,
        )
    except (TimeoutError, OSError) as exc:
        print(
            f"Network error calling Gmail API ({exc}). "
            "Check internet/VPN/firewall; script prefers IPv4 for Google APIs.",
            file=sys.stderr,
        )
        sys.exit(1)
    except HttpError as exc:
        print(f"Gmail API error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Sent. message_id={msg_id}")
    print(f"Next: TaskBot login as {recipient} → Sync → Tasks / Conflicts.")


def send_batch(
    names: list[str],
    *,
    unique_subject: bool,
    dry_run: bool,
    delay: float,
) -> None:
    batch_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    print(f"Batch: {len(names)} fixture(s), stamp={batch_stamp}")
    if dry_run:
        for i, name in enumerate(names, 1):
            print(f"\n--- [{i}/{len(names)}] {name} ---")
            subject, body = _resolve_fixture(name)
            send_email(
                subject=subject,
                body=body,
                fixture_name=name,
                unique_subject=unique_subject,
                batch_stamp=batch_stamp,
                dry_run=True,
            )
        return

    _load_env()
    sender = _require_env("GMAIL_TEST_SENDER")
    recipient = _require_env("GMAIL_TEST_RECIPIENT")
    service = get_gmail_service()

    ok = 0
    for i, name in enumerate(names, 1):
        subject, body = _resolve_fixture(name)
        print(f"\n[{i}/{len(names)}] {name}")
        try:
            msg_id = _send_one(
                service,
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                fixture_name=name,
                unique_subject=unique_subject,
                batch_stamp=batch_stamp,
            )
            print(f"  Sent message_id={msg_id}")
            ok += 1
        except (TimeoutError, OSError) as exc:
            print(f"  FAILED (network): {exc}", file=sys.stderr)
        except HttpError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
        if delay > 0 and i < len(names):
            time.sleep(delay)

    print(f"\nBatch done: {ok}/{len(names)} sent → sync inbox {recipient}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send test Gmail A → B for TaskBot sync.")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow for sender account")
    parser.add_argument(
        "--debug-oauth",
        action="store_true",
        help="Print client_id + redirect_uri + auth URL (no browser)",
    )
    parser.add_argument("--list-fixtures", action="store_true", help="List bundled fixtures")
    parser.add_argument(
        "--category",
        choices=("high_confidence", "normal"),
        help="Filter fixtures by category (with --batch or --list-fixtures)",
    )
    parser.add_argument("--fixture", help="Single fixture name from manifest.json")
    parser.add_argument("--batch", action="store_true", help="Send all fixtures (or --category subset)")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between batch sends (default 3)")
    parser.add_argument("--subject", help="Email subject (with --body-file)")
    parser.add_argument("--body-file", type=Path, help="Plain-text body file")
    parser.add_argument(
        "--no-unique-subject",
        action="store_true",
        help="Do not append stamp/fixture id (may hit TaskBot content_hash dedup)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload without sending")
    args = parser.parse_args()

    if args.list_fixtures:
        _list_fixtures(category=args.category)
        return

    if args.debug_oauth:
        _load_env()
        creds_path, _ = _paths()
        _print_oauth_debug(creds_path)
        return

    if args.auth:
        _load_env()
        _require_env("GMAIL_TEST_SENDER")
        get_gmail_service(force_auth=True)
        print("OAuth OK. Token ready for --fixture / --batch sends.")
        return

    unique = not args.no_unique_subject

    if args.batch:
        names = _fixture_names(category=args.category)
        if not names:
            print("No fixtures to send.", file=sys.stderr)
            sys.exit(1)
        send_batch(names, unique_subject=unique, dry_run=args.dry_run, delay=max(0.0, args.delay))
        return

    if args.fixture:
        subject, body = _resolve_fixture(args.fixture)
        send_email(
            subject=subject,
            body=body,
            fixture_name=args.fixture,
            unique_subject=unique,
            dry_run=args.dry_run,
        )
        return

    if args.subject and args.body_file:
        path = args.body_file if args.body_file.is_absolute() else ROOT / args.body_file
        if not path.exists():
            print(f"Body file not found: {path}", file=sys.stderr)
            sys.exit(1)
        send_email(
            subject=args.subject,
            body=path.read_text(encoding="utf-8"),
            unique_subject=unique,
            dry_run=args.dry_run,
        )
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
