# TaskBot Cloud Setup Guide (GCP + AWS)

This guide covers all required setup before running TaskBot end-to-end.

## 1) GCP Setup (OAuth + APIs)

### 1.1 Create project and enable APIs
- Create or select a GCP project.
- Enable:
  - Gmail API
  - Google Drive API
  - Google Calendar API
  - People API (optional, for profile info)

### 1.2 Configure OAuth consent screen
- User type: External (or Internal if only workspace users).
- App name: TaskBot.
- Add scopes:
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

## 2) AWS Setup (EC2 + IAM User Keys + S3)

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
- Create bucket for uploads (for example `taskbot-uploads-dev`).
- Enable block public access.
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
- `backend-api` via systemd (`taskbot-backend-api`)
- `agent-module` via systemd (`taskbot-agent-worker`)
- `frontend` via PM2 (`taskbot-frontend`)
- Nginx reverse proxy:
  - `/` -> frontend
  - `/api` -> backend-api

---

## 3) Environment Variables Checklist

Minimum required in `.env`:
- Google:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
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

---

## 4) Validation Steps

- OAuth URL works: `GET /auth/google`
- Callback succeeds with token exchange: `GET /auth/callback?code=...`
- Backend health: `GET /health`
- Migration runs on EC2: `alembic upgrade head`
- Worker starts and schedules jobs
- Frontend served via Nginx

If OAuth fails with `redirect_uri_mismatch`, re-check redirect URI in GCP console and `.env`.
