# TaskBot Cloud Setup Guide (Google APIs + AWS)

This guide covers all required setup before running TaskBot end-to-end.

## Local dev & single-host deploy: Docker Compose (full stack)

- Root `docker-compose.yml` runs **Postgres 15, Redis 7, backend API, agent worker, Next.js (dev)**. Copy `.env.example` → `.env`, fill secrets, then:
  - `./scripts/docker_infra.sh up` — build + start all services.
  - `./scripts/docker_infra.sh up-db` — only Postgres + Redis (if you run Python/Node on the host).
- Compose **overrides** `DATABASE_URL`, `REDIS_URL`, and `BACKEND_API_BASE_URL` for in-network service names; `.env` still supplies OAuth, AWS, Groq, Clerk, MCP URLs, etc.
- If host ports **5432** or **6379** are busy, set `POSTGRES_PUBLISH_PORT` / `REDIS_PUBLISH_PORT` in `.env` (see `.env.example`).
- **Production on EC2:** install Docker + Compose plugin, clone repo, place `.env`, run `scripts/deploy_stack.sh` (see `docs/dev.md` §11). Optional: Nginx on the host in front of published ports. Legacy non-Docker deploy remains `deploy.sh` + systemd.

## Quick decision: do you still need GCP?

- You do **not** need GCP for LLM anymore (project uses Groq now).
- You **still need** Google Cloud project if you use:
  - Gmail sync
  - Google Drive sync
  - Google Calendar event/reminder
- If you do not use those Google integrations, you can skip Google Cloud setup and run upload-only flow.

## 1) Clerk Setup (Session Auth)

### 1.1 Create Clerk application
- Create app in Clerk Dashboard.
- Enable authentication methods you want (email, Google social login, etc.).
- Copy:
  - Publishable key (`pk_...`) — use `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (Next.js) or `VITE_CLERK_PUBLISHABLE_KEY` (Vite) in `.env`
  - `CLERK_SECRET_KEY`

### 1.2 Add Clerk values to `.env`
- `CLERK_SECRET_KEY`
- Publishable key (choose one, depending on your frontend bundler):
  - Next.js: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  - Vite: `VITE_CLERK_PUBLISHABLE_KEY`

---

## 2) Google Cloud Setup (OAuth + Google APIs)

### 1.1 Create project and enable APIs
- Create or select a GCP project.
- Enable only these APIs for TaskBot:
  - Gmail API
  - Google Drive API
  - Google Calendar API
  - People API (optional, for profile info)

### 1.2 Configure OAuth consent screen
- User type: External (or Internal if only workspace users).
- App name: TaskBot.
- Add scopes (minimum set for this product):
  - `openid`
  - `email`
  - `profile`
  - `https://www.googleapis.com/auth/gmail.readonly`
  - `https://www.googleapis.com/auth/drive.readonly`
  - `https://www.googleapis.com/auth/calendar.events`
- Add test users while app is in testing mode.

### 1.3 Create OAuth client credentials
- Create credentials -> OAuth client ID -> Web application.
- Add Authorized redirect URI:
  - `http://localhost:8000/auth/callback` (local)
  - `https://<your-domain>/api/auth/callback` (production)
- Copy values:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`

### 1.4 Add GCP values to `.env`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

---

### 1.5 Cost notes (important)

- For this project, Google Cloud is used mainly for OAuth + Google Workspace APIs.
- With personal/testing usage, cost is usually low or zero if within free quota.
- You can keep costs down by:
  - limiting sync interval
  - using test users only during development
  - enabling only required APIs
  - setting quota alerts in GCP

## 3) AWS Setup (EC2 + IAM User Keys + S3)

## 2.1 Create IAM user for programmatic access
- AWS Console -> IAM -> Users -> Create user.
- Enable **Programmatic access** (Access key).
- Attach policy (minimum):
  - S3 bucket access for uploads
  - CloudWatch logs (optional)
- Save:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`

Never commit these keys to git. Only store in `.env` or AWS Systems Manager Parameter Store.

### 2.2 Create S3 bucket
- Create bucket for uploads (for example `taskbot-uploads-dev` or your chosen name matching `AWS_S3_BUCKET`).
- Enable block public access.
- **No need to pre-create “folders”** in the console: the app writes keys like `{user_uuid}/{upload_id}.pdf` on first upload; an empty bucket is enough.
- Optional lifecycle:
  - Auto-delete processed uploads after 30 days.
- Add to env:
  - `AWS_REGION`
  - `AWS_S3_BUCKET`

### 2.3 Provision EC2 instance
- Ubuntu 22.04 LTS
- Security group:
  - 22 (SSH) from your IP
  - 80 (HTTP) from anywhere
  - 443 (HTTPS) from anywhere
- Install:
  - Python 3.11
  - Node.js 18+
  - PostgreSQL 15
  - Redis
  - Nginx
  - PM2

### 2.4 Services layout on EC2
- `backend` via systemd (`taskbot-backend`)
- `agent` via systemd (`taskbot-agent-worker`)
- `frontend` via PM2 (`taskbot-frontend`)
- Nginx reverse proxy:
  - `/` -> frontend
  - `/api` -> backend

---

## MCP endpoint URLs (Gmail / Drive / Calendar)

- **Gmail / Calendar:** TaskBot dùng **HTTP MCP client** trong `agent/app/mcp/` tới server **hosted** (Anthropic) — URL trong `.env.example`.
- **Google Drive:** Trong repo có **`drive-mcp-server/`** — FastAPI làm **HTTP MCP server** (cùng contract với `BaseMCPClient`), proxy sang **Google Drive API v3** bằng **Bearer token của user** (OAuth TaskBot). Với `docker compose`, service **`mcp-drive`** chạy sẵn; agent trong compose nhận `DRIVE_MCP_URL=http://mcp-drive:8787/mcp` tự động.
- **Lưu ý:** Đây là HTTP MCP (giống hosted Gmail/Calendar), không phải MCP stdio dùng trong Claude Desktop.

---

## 4) Environment Variables Checklist

Minimum required in `.env`:
- Google:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
- Clerk:
  - `CLERK_SECRET_KEY`
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (Next.js) or `VITE_CLERK_PUBLISHABLE_KEY` (Vite)
- LLM:
  - `GROQ_API_KEY`
  - `GROQ_MODEL`
- Database/Redis:
  - `DATABASE_URL`
  - `REDIS_URL`
- Security:
  - `JWT_SECRET`
  - `ENCRYPTION_KEY`
- App:
  - `SYNC_GMAIL_INTERVAL_MINUTES`
  - `SYNC_DRIVE_INTERVAL_MINUTES`
- AWS:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_REGION`
  - `AWS_S3_BUCKET`
- MCP (agent):
  - `GMAIL_MCP_URL`
  - `DRIVE_MCP_URL` (must be reachable; see MCP section above)
  - `CALENDAR_MCP_URL`
  - `BACKEND_API_BASE_URL`

---

## 5) Validation Steps

- With stack up: `docker compose ps` — `backend` healthy, `mcp-drive` healthy, `agent` running, `frontend` listening (hoặc chạy `./scripts/verify_stack.sh`).
- Run from repo root: `./.venv/bin/python scripts/validate_env.py` (full check against **host-published** ports), or `... --dev` when not everything is running.
- If you see **S3 bucket 404**: bucket not created yet on AWS — create it, then re-run the script.
- Clerk sign-in works on frontend
- OAuth URL works: `GET /auth/google` (after user is signed in)
- Callback succeeds with token exchange: `GET /auth/callback?code=...`
- Backend health: `GET /health` (migrations run automatically when the **backend** container starts)
- Agent worker schedules jobs; MCP URLs reachable from the **agent** container (Drive MCP may require `host.docker.internal` or extra_hosts — see `docs/dev.md` if needed)
- Production: optional Nginx in front of Compose-published ports, or legacy systemd (`deploy.sh`)

If OAuth fails with `redirect_uri_mismatch`, re-check redirect URI in GCP console and `.env`.

---

## 6) If you want zero Google Cloud usage

You can run a reduced mode:
- disable Gmail/Drive polling jobs
- skip Calendar notifications
- use only file upload pipeline

In that mode, Google OAuth/API setup is not required.
