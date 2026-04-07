# TaskBot — Run the product from scratch

This guide walks you from an empty checkout to a **running TaskBot**: databases, API, background worker, Drive bridge, and web app. After you finish, you can sign in with Google, sync Gmail/Drive, and manage tasks in the dashboard.

Product overview: [`README.md`](../README.md). Scripted demo with `curl` steps: [`docs/demo-flow.md`](demo-flow.md).

---

## 1. Prerequisites

On your machine you need:

- **Docker** and **Docker Compose** (used to run the full stack).
- A **Google Cloud** project with an OAuth client (Gmail / Drive / Calendar as you need).
- A **Groq API key** for the LLM pipeline.

Optional: **AWS S3** credentials and bucket only if you use file **upload** in the app.

---

## 2. Repository and environment file

```bash
cd /path/to/taskExtractor
cp .env.example .env
```

Edit **`.env`** at the repository root. The backend and agent read this file; Docker Compose also mounts it into containers.

Set at least:

| Variable | Role |
|----------|------|
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | OAuth; redirect is often `http://localhost:8000/auth/callback` |
| `FRONTEND_URL` | Where the browser loads the app, e.g. `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | API URL the **browser** calls, e.g. `http://127.0.0.1:8000` |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODEL` | Extraction and normalization |
| `JWT_SECRET` | Signs API JWTs after login |
| `ENCRYPTION_KEY` | Fernet key for Google tokens stored in Postgres |

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For **uploads**, add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_S3_BUCKET`.

In **Google Cloud Console → APIs & Services → Credentials → your OAuth client**, add an **Authorized redirect URI** that matches `GOOGLE_REDIRECT_URI` exactly.

Compose overrides `DATABASE_URL`, `REDIS_URL`, and in-container `BACKEND_API_BASE_URL` so services talk to each other. You do not need to edit those for the default Docker setup.

---

## 3. Start TaskBot

From the repository root:

```bash
./scripts/docker_infra.sh up
```

This builds and starts **Postgres**, **Redis**, **Drive MCP**, **backend API**, **agent worker**, and **frontend**. Wait until containers report healthy (first build can take several minutes).

Default URLs:

| What | URL |
|------|-----|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API health | http://localhost:8000/health |
| Drive MCP health | http://localhost:8787/health |

If the repo has `./scripts/verify_stack.sh`, you can run it for smoke checks.

---

## 4. Use the product

1. Open **http://localhost:3000**.
2. Use **Continue with Google** and complete OAuth.
3. You should land on the **Tasks** dashboard. From there you can sync sources, review extracted tasks, handle conflicts, and use settings as implemented in the UI.

The agent worker pulls jobs from Redis and talks to Gmail/Drive/Calendar via MCP; the API serves the frontend and persists data in Postgres.

---

## 5. Day-to-day commands

```bash
./scripts/docker_infra.sh logs backend    # follow API logs
./scripts/docker_infra.sh logs agent      # worker / pipeline
./scripts/docker_infra.sh logs frontend
./scripts/docker_infra.sh down            # stop containers
./scripts/docker_infra.sh down-volumes    # stop and delete DB/Redis volumes (data loss)
```

---

## 6. When something fails

**Database password errors (e.g. `password authentication failed for user "taskbot"`)**  
Postgres must be up (`./scripts/docker_infra.sh up` or `up-db`). Default Compose credentials are user `taskbot`, password `taskbot`, database `taskbot`. If you changed passwords after the volume was first created, the old password remains until you align `DATABASE_URL` or remove volumes with `down-volumes` and recreate.

**Running Alembic on the host** (not inside the backend container)  
With a venv and dependencies installed, from `backend/`: `alembic upgrade head`. Alembic loads the repo-root `.env`; on host it prefers that file over stale shell exports, while inside Docker it keeps Compose-provided env vars.

---

## Appendix — Develop on the host (hot reload)

Keep **Postgres** and **Redis** in Docker, run app processes locally:

```bash
./scripts/docker_infra.sh up-db
```

Then:

```bash
cd /path/to/taskExtractor
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

In `.env`, point services at published ports, for example `DATABASE_URL=postgresql+asyncpg://taskbot:taskbot@localhost:5432/taskbot`, `REDIS_URL=redis://localhost:6379/0`, `BACKEND_API_BASE_URL=http://127.0.0.1:8000`, `DRIVE_MCP_URL=http://127.0.0.1:8787/mcp` (start `mcp-drive` via Compose or run `drive-mcp-server` separately).

Terminal 1 — API:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — agent (from repo root):

```bash
export PYTHONPATH=agent
python -m app.scheduler.worker
```

Terminal 3 — frontend:

```bash
cd frontend
npm install && npm run dev
```

---

## Contributors — tests and eval

```bash
# Backend (from backend/)
python -m pytest tests/unit -q

# Agent (from agent/)
python -m pytest tests/ -q

# Drive MCP (from drive-mcp-server/)
python -m pytest tests/ -q
```

From the repository root with a venv:

```bash
python tests/eval/run_eval.py --method rule     --output tests/eval/results/rule.json
python tests/eval/run_eval.py --method single   --output tests/eval/results/single_llm_70b.json
python tests/eval/run_eval.py --method pipeline --output tests/eval/results/pipeline.json
python tests/eval/compare_results.py tests/eval/results/rule.json tests/eval/results/single_llm_70b.json tests/eval/results/pipeline.json
```

Groq quotas may require `GROQ_FALLBACK_MODEL` or splitting runs; see `tests/eval/results/*_report.md` when present.

---

## Related docs

| File | Content |
|------|---------|
| [`README.md`](../README.md) | Product description |
| [`demo-flow.md`](demo-flow.md) | Step-by-step demo and `curl` |
| [`dev.md`](dev.md) | Architecture and schema |
| [`setup-cloud.md`](setup-cloud.md) | Cloud, OAuth, AWS |
| [`tracking.md`](tracking.md) | Project checklist |
| [`.env.example`](../.env.example) | Full variable list |
