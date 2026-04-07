# TaskBot — Demo flow

Use this as a **3–5 minute** walkthrough for supervisors or defense. Adjust timing if the committee asks to go deeper.

**Full run instructions:** [`run-guide.md`](run-guide.md)

---

## Run the environment (do this once before any scene)

From the **repository root** (where `docker-compose.yml` lives):

1. **Configure**

   ```bash
   cp .env.example .env
   # Edit .env: Google OAuth, GROQ_API_KEY, JWT_SECRET, ENCRYPTION_KEY, FRONTEND_URL, NEXT_PUBLIC_API_URL, AWS_* if using Upload
   ```

2. **Start full stack**

   ```bash
   ./scripts/docker_infra.sh up
   ```

   Default URLs (override with `BACKEND_PUBLISH_PORT`, `FRONTEND_PUBLISH_PORT`, etc. in `.env`):

   | Service | URL |
   |--------|-----|
   | Frontend | `http://localhost:${FRONTEND_PUBLISH_PORT:-3000}` |
   | Backend API | `http://localhost:${BACKEND_PUBLISH_PORT:-8000}` |
   | Drive MCP health | `http://localhost:${MCP_DRIVE_PUBLISH_PORT:-8787}/health` |
   | Postgres | `localhost:${POSTGRES_PUBLISH_PORT:-5432}` (user `taskbot`, db `taskbot`) |
   | Redis | `localhost:${REDIS_PUBLISH_PORT:-6379}` |

3. **Watch logs (optional, in another terminal)**

   ```bash
   ./scripts/docker_infra.sh logs backend
   ./scripts/docker_infra.sh logs agent
   ./scripts/docker_infra.sh logs frontend
   ```

4. **Stop when finished**

   ```bash
   ./scripts/docker_infra.sh down
   ```

**Host-only dev (no Compose):** start Postgres + Redis yourself, run Alembic migrations on `backend`, run `uvicorn` for backend, worker for `agent`, `npm run dev` in `frontend`. Use the same `NEXT_PUBLIC_API_URL` and `FRONTEND_URL` as in `.env`.

---

## Before you start (pre-flight)

1. **Stack running** — commands above.
2. **`.env` filled** — especially Google OAuth, Groq, JWT/Fernet keys, `FRONTEND_URL`, `NEXT_PUBLIC_API_URL`.
3. **Google OAuth** — Authorized redirect URI in Google Cloud Console exactly matches `GOOGLE_REDIRECT_URI` (e.g. `http://localhost:8000/auth/callback`).
4. **Test account** — A Gmail/Drive account with at least one clear “action item” email or doc (optional but best for live sync).
5. **Backup plan** — If the network or Google fails, use **Upload** (scene 8) with a small PDF/DOCX, or show empty Tasks/Sync and narrate.

---

## Flow A — Full story (~4 minutes)

Replace `FE` with your frontend base URL (e.g. `http://localhost:3000`) and `API` with your API base (e.g. `http://127.0.0.1:8000`). For terminal snippets:

```bash
export API=http://127.0.0.1:8000
export TOKEN=   # paste JWT after login (localStorage key taskbot_token)
```

### 1) Open the product (30 s)

**What to say:** *“This is the dashboard; everything goes through our API and a background agent.”*

**How to run**

- Start stack (see top of this doc).
- Open in browser: **`FE`** (e.g. `http://localhost:3000`).
- If you are sent to login, that is expected when not authenticated.

---

### 2) Sign in (45 s)

**What to say:** *“OAuth hits the FastAPI backend; the SPA gets a JWT, not Google tokens in the browser.”*

**How to run**

- Open **`FE/login`** (e.g. `http://localhost:3000/login`).
- Click **Continue with Google** — browser goes to **`API/auth/google`** (redirect chain to Google, then back to **`API/auth/callback`**, then redirect to **`FE/auth/callback#access_token=…`**).
- After success, app navigates to **`FE/tasks`**.

**Sanity check (no UI):** after OAuth, API must accept the JWT:

```bash
# Replace TOKEN with the JWT from browser devtools → Application → Local Storage → taskbot_token
curl -s -H "Authorization: Bearer TOKEN" "$API/auth/me"
```

---

### 3) Sync status (30 s)

**What to say:** *“Scheduler jobs enqueue work on Redis; manual trigger is on the Sync page.”*

**How to run**

- From any logged-in page, look at the **header** (right): idle / syncing / error dot.
- Open **`FE/sync`** (sidebar **Sync**).

**API equivalent (optional)**

```bash
curl -s -H "Authorization: Bearer TOKEN" "$API/sync/status" | python -m json.tool
```

---

### 4) Trigger ingestion (60 s)

**What to say:** *“Each run is logged; the agent pulls via MCP, then runs the LangGraph pipeline.”*

**How to run**

- Stay on **`FE/sync`**.
- Click **Sync Gmail now** and/or **Sync Drive now** (requires Google connected for that user).
- Watch source rows for **running** → **idle**; table **Recent pipeline runs** updates (page auto-refreshes ~15s, or click **Refresh**).

**Logs (recommended while demoing)**

```bash
./scripts/docker_infra.sh logs agent
```

**API equivalent**

```bash
curl -s -X POST -H "Authorization: Bearer TOKEN" "$API/sync/trigger?source=gmail"
curl -s -X POST -H "Authorization: Bearer TOKEN" "$API/sync/trigger?source=drive"
curl -s -H "Authorization: Bearer TOKEN" "$API/sync/history?limit=10" | python -m json.tool
```

---

### 5) Tasks (60 s)

**What to say:** *“Extraction and normalization are LLM-based; validation adds missing-field hints and conflict linkage.”*

**How to run**

- Open **`FE/tasks`**.
- Use **Status** / **Source** dropdowns and **Sort**; list reloads in place.
- **Confirm** / **Dismiss** on a row (PATCH via API under the hood).

**API equivalent**

```bash
curl -s -H "Authorization: Bearer TOKEN" "$API/tasks?limit=20" | python -m json.tool
```

---

### 6) Task detail (30 s)

**What to say:** *“User corrections stay in Postgres; calendar hooks are in the architecture doc.”*

**How to run**

- On **`FE/tasks`**, click a **task title**.
- URL shape: **`FE/tasks/<uuid>`** (copy `id` from list or API).
- Edit **deadline** (`YYYY-MM-DD`), click **Save**.

**API equivalent**

```bash
TASK_ID="<paste-uuid>"
curl -s -H "Authorization: Bearer TOKEN" "$API/tasks/$TASK_ID" | python -m json.tool
curl -s -X PATCH -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"deadline":"2026-12-31"}' "$API/tasks/$TASK_ID" | python -m json.tool
```

---

### 7) Conflicts (45 s) — if any exist

**What to say:** *“Conflicts are first-class records; resolution is explicit.”*

**How to run**

- Open **`FE/conflicts`**.
- If empty: skip or say conflicts appear when the pipeline detects clashing tasks; run more syncs or use seeded data.
- Resolve with **Use source A / B** or **Dismiss**.

**API equivalent**

```bash
curl -s -H "Authorization: Bearer TOKEN" "$API/tasks/conflicts?resolved=false" | python -m json.tool
# CONFLICT_ID="<uuid>"
curl -s -X PATCH -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"resolution":"dismiss"}' "$API/tasks/conflicts/$CONFLICT_ID" | python -m json.tool
```

---

### 8) Upload (30 s) — optional

**What to say:** *“Uploads go to S3 and the same pipeline runs as for Gmail/Drive.”*

**How to run**

- Open **`FE/upload`**.
- Drag a **.pdf** or **.docx** (≤ 10 MB), or **Browse**.
- Requires valid **AWS** credentials and bucket in `.env`; watch **Upload ID** and **Status** on the page.

**API equivalent**

```bash
curl -s -X POST -H "Authorization: Bearer TOKEN" -F "file=@/path/to/file.pdf" "$API/upload" | python -m json.tool
# UPLOAD_ID="<from response>"
curl -s -H "Authorization: Bearer TOKEN" "$API/upload/$UPLOAD_ID/status" | python -m json.tool
```

---

### 9) Settings (20 s)

**What to say:** *“Intervals are persisted per user; disconnect clears the stored OAuth bundle on the server.”*

**How to run**

- Open **`FE/settings`**.
- Change **Gmail** / **Drive** interval (minutes), **Save intervals**.
- **Disconnect Google** only if you are fine re-linking before the next sync demo.

**API equivalent**

```bash
curl -s -H "Authorization: Bearer TOKEN" "$API/settings" | python -m json.tool
curl -s -X PATCH -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"gmail_interval":15,"drive_interval":30}' "$API/settings" | python -m json.tool
```

---

### 10) Close (15 s)

**What to say:** *“Evaluation on a synthetic labeled set is in `tests/eval/results/`; production quality depends on Groq model and prompts.”*

**How to run**

- No command; optionally open the repo folder `tests/eval/results/` in the IDE or show `comparison_report.md` on screen.

---

## Flow B — API / pipeline only (no UI, ~2 minutes)

| Step | How to run |
|------|------------|
| Health | `curl -s http://localhost:8000/health` |
| OAuth JSON (tests) | `curl -s "http://localhost:8000/auth/callback?code=...&as_json=true"` (use a real code from Google in dev only; normally use UI) |
| Agent activity | `./scripts/docker_infra.sh logs agent` after `POST /sync/trigger` with a valid token |
| Eval smoke | From repo root, venv on: `python tests/eval/run_eval.py --method rule --limit 5 --output /tmp/demo_eval.json` |

---

## Questions you may get (short answers)

| Question | Direction |
|----------|-----------|
| Where is the “AI”? | Groq LLM inside **agent** pipeline nodes (extract → normalize → validate); not in the Next.js app. |
| Why MCP? | Gmail/Calendar use hosted MCP HTTP; Drive uses **drive-mcp-server** in this repo. |
| Data isolation? | API filters by authenticated **user_id**; tokens encrypted at rest. |
| What if Groq rate-limits? | `GROQ_FALLBACK_MODEL` and backoff in `agent/app/pipeline/llm.py`; eval may use smaller model or split runs. |

---

## Checklist (printable)

- [ ] `./scripts/docker_infra.sh up` (or equivalent) done
- [ ] `FE` and `API` open in notes; `NEXT_PUBLIC_API_URL` matches browser-reachable API
- [ ] Frontend loads
- [ ] Login with Google succeeds
- [ ] Sync page shows sources + can trigger Gmail/Drive
- [ ] At least one task appears (sync or upload)
- [ ] Task detail + optional conflict or upload path rehearsed once

---

## After the demo

- Note any **404 / 429 / CORS** errors and capture **backend + agent** log lines for debugging.
- For thesis: paste **tables** from `tests/eval/results/comparison_report.md` into the evaluation chapter.
