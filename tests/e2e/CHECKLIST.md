# TaskBot E2E Test Checklist

Real Gmail/Drive account. No mock data. Run against a locally-running stack
(`docker compose up` or host-side backend + agent + worker).

> **Automated hero-scenario coverage** (deterministic, no live account, no LLM
> quota) lives alongside this manual checklist:
> - `agent/tests/e2e/test_hero_scenarios.py` — multi-source conflict (scenario 1)
>   and smart auto-confirm through the full pipeline (scenario 3)
> - `backend/tests/integration/test_hero_merge_e2e.py` — thread-update merge +
>   calendar resync against real Postgres (scenario 2; auto-skips if DB down)
>
> Real-vs-synthetic validation scope is documented in
> [`real-world-validation.md`](./real-world-validation.md). The flows below are
> the full-stack manual walkthroughs against a real Google account.

## Prerequisites

```bash
# 1. Stack up
docker compose up -d

# 2. Set env vars (never commit these)
export E2E_BASE_URL=http://127.0.0.1:8000       # backend API
export E2E_GOOGLE_ACCESS_TOKEN=<oauth_token>    # gmail.readonly + drive.readonly + calendar
export E2E_JWT_TOKEN=<taskbot_jwt>              # issued after OAuth login to TaskBot
export E2E_USER_EMAIL=sh1rohasbeencursed@gmail.com

# Alternatively: load from .env.e2e (gitignored)
```

How to get `E2E_GOOGLE_ACCESS_TOKEN` (dev only):
- Google OAuth Playground → Gmail + Drive + Calendar scopes
- Or copy from TaskBot backend OAuth response (network tab, short-lived ~1h)

How to get `E2E_JWT_TOKEN`:
- Open TaskBot frontend → login with Google → DevTools → Application → copy `access_token` cookie/localStorage

Automated runner for Flow 1:

```bash
python scripts/e2e_gmail_sync.py          # Flow 1 happy path
python scripts/e2e_gmail_sync.py --help
```

---

## Flow 1 — Gmail Sync Happy Path

**Goal**: one manual trigger → pipeline processes emails → ≥1 task visible in dashboard.

### Setup

- [ ] Google account has ≥1 real email in primary inbox containing an explicit task assignment
  (e.g. "Anh Minh ơi, deadline báo cáo quý 2 là thứ Sáu này nhé")
- [ ] Backend running, Redis running, agent worker running
- [ ] User has connected Google account in TaskBot Settings

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | `GET /sync/status` | response 200, gmail row `status != "running"` |
| 2 | `POST /sync/trigger?source=gmail&time_range=1d` | `{"status":"queued","source":"gmail"}` |
| 3 | Poll `GET /sync/progress?source=gmail` every 2s up to 60s | `active:true` then `active:false` when done |
| 4 | `GET /sync/status` | gmail row `status = "idle"`, `last_synced_at` updated |
| 5 | `GET /tasks?source=gmail&status=pending` | ≥1 task returned |
| 6 | Each task has `title` (non-empty), `confidence ≥ 0.55` | |
| 7 | Tasks from THIS sync have `created_at` within last 2 min | |

### Pass criteria

- [ ] At least 1 task extracted
- [ ] No task with `confidence < 0.55` (abstain threshold)
- [ ] `GET /sync/history` shows a `PipelineRun` with `status="completed"` for this run
- [ ] Re-triggering the same sync immediately returns 409 `SYNC_IN_PROGRESS` or deduplication
  (same `source_ref` → no duplicate tasks)

### Edge cases to test manually

- [ ] Trigger sync when sync already running → 409 `SYNC_IN_PROGRESS`
- [ ] Disconnect Google in Settings → trigger → 400 `NO_GOOGLE_TOKEN`
- [ ] Inbox 0 (no new emails) → sync completes cleanly, no tasks extracted, no error

---

## Flow 2 — Drive Sync Happy Path

**Goal**: Drive sync picks up a Google Doc containing task assignments.

### Setup

- [ ] Google Drive has ≥1 Doc/Sheet modified in the last 24h with explicit assignments
  (e.g. a meeting notes doc with a checklist)

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | `POST /sync/trigger?source=drive&time_range=1d` | `{"status":"queued","source":"drive"}` |
| 2 | Poll `GET /sync/progress?source=drive` up to 90s | completes without error |
| 3 | `GET /tasks?source=drive&status=pending` | ≥1 task returned |
| 4 | Task `title` matches assignable content from the doc | |

### Pass criteria

- [ ] Tasks extracted from Drive have `source_type = "drive"` (via `GET /tasks/:id`)
- [ ] Owned and shared files both processed (sync_profile=balanced)
- [ ] Dedup: same Drive file processed twice → no duplicate tasks (content_hash check)

---

## Flow 3 — File Upload → Extract

**Goal**: direct upload of a document triggers pipeline without Gmail/Drive OAuth.

### Setup

- [ ] Prepare a `.txt` or `.pdf` file with 2–3 explicit task assignments and deadlines
- [ ] AWS S3 (or LocalStack) configured

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | `POST /upload` multipart `file=<your_file.txt>` | `{"upload_id":"...","status":"queued"}` |
| 2 | Poll `GET /upload/{upload_id}/status` every 2s up to 60s | status transitions: `queued → processing → done` |
| 3 | `GET /tasks?source=upload&status=pending` | tasks extracted from file content |
| 4 | Task `deadline` correctly parsed from file text | |

### Pass criteria

- [ ] Upload returns `upload_id` immediately (non-blocking)
- [ ] Status reaches `done` within 60s
- [ ] Empty file → 400 `EMPTY_FILE`
- [ ] Unsupported extension (`.exe`) → 400 `UNSUPPORTED_FILE`
- [ ] Uploading the same file twice → second upload gets same `content_hash`, no duplicate tasks

---

## Flow 4 — Conflict Detection (Two Contradicting Emails)

**Goal**: two emails about the same task with different deadlines surface a conflict.

### Setup

Send two real emails (or use existing ones) to the test account:
- Email A: "Anh Minh, gửi báo cáo Q2 trước thứ Năm nhé"
- Email B (same thread or similar subject): "Anh Minh, deadline báo cáo Q2 dời sang thứ Hai tuần sau"

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | Sync Gmail (Flow 1 steps 2–4) | both emails processed |
| 2 | `GET /conflicts?resolved=false` | ≥1 conflict with `conflict_type="deadline_conflict"` |
| 3 | Inspect conflict: `task_a.title` ≈ `task_b.title`, different `deadline` | |
| 4 | `PATCH /conflicts/{conflict_id}` body `{"resolution":"keep_latest"}` | 200, `resolved=true` |
| 5 | `GET /conflicts/{conflict_id}` | `resolved=true`, description contains `[resolved:keep_latest]` |
| 6 | Attempt re-resolve same conflict | 409 `ALREADY_RESOLVED` |

### Pass criteria

- [ ] Conflict detected within same pipeline run (intra-batch) or across runs (inter-doc)
- [ ] Both task entries present with distinct `source_ref`
- [ ] Resolved conflict not re-surfaced on next sync

---

## Flow 5 — Calendar Notification Dispatch

**Goal**: task with a deadline gets a Google Calendar event created automatically.

### Setup

- [ ] Google Calendar scope included in OAuth token
- [ ] `CALENDAR_MCP_URL` reachable
- [ ] Test email contains a task with an explicit date ("nộp báo cáo ngày 20/5")

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | Trigger Gmail sync (Flow 1) | pipeline runs |
| 2 | `GET /tasks?source=gmail` | find a task with non-null `deadline` |
| 3 | Check `task.calendar_event_id` | non-null after pipeline completes |
| 4 | `GET /calendar/events?start=<deadline>&end=<deadline>` | event returned |
| 5 | Open Google Calendar in browser for the test account | event visible on the correct date |
| 6 | Update task deadline: `PATCH /tasks/{id}` `{"deadline":"<new_date>"}` | |
| 7 | Re-trigger sync or re-process document | `calendar_event_id` unchanged, event date updated |

### Pass criteria

- [ ] `calendar_event_id` populated on task within 5s of pipeline completion
- [ ] Calendar event title matches task title
- [ ] Task without deadline → `calendar_event_id` stays null, no Calendar API call
- [ ] Calendar MCP 5xx → pipeline does NOT crash (fail-safe dispatch node)

---

## Flow 6 — Auth Revoke Handling

**Goal**: revoked Google token is detected gracefully; auto-sync suspended, user prompted.

### Setup

- [ ] Revoke token: Google Account Settings → Security → Manage Third-party access → Remove TaskBot
- [ ] Or use `scripts/mcp_real_account_check.py` with an expired token

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | Trigger Gmail sync with revoked/expired token | |
| 2 | `POST /sync/trigger?source=gmail&time_range=1d` | might return 401 `GOOGLE_AUTH_EXPIRED` immediately (token refresh fails) |
| 3 | If job was queued: worker encounters 401 from MCP | |
| 4 | Check Redis key `sync:disabled:<user_id>:gmail` | set after streak ≥ threshold (default 3) |
| 5 | On subsequent auto-sync trigger: | worker skips, returns early |
| 6 | Check `record_pipeline_error` in observability | `source_type="mcp_auth_revoked"` recorded |
| 7 | Reconnect Google in Settings → `POST /sync/clear` | `sync:disabled` key cleared |
| 8 | Trigger sync again | succeeds |

### Pass criteria

- [ ] After revoke: backend returns 401 with `GOOGLE_AUTH_EXPIRED` on trigger (token refresh path)
- [ ] If job queued before revoke: worker marks auth streak, suspends auto-sync after N failures
- [ ] No pipeline crash — errors recorded, not raised
- [ ] After reconnect + clear: sync resumes normally

---

## Flow 7 — Rate Limit → Fallback → Recovery

**Goal**: Groq primary model hits rate limit; pipeline falls back to Llama/Gemini; tasks still extracted.

> **Note**: Hard to trigger with a single user. Use `GROQ_STRICT_PRIMARY=1` + a known-exhausted key,
> or mock via `GROQ_DISABLE_GEMINI_FALLBACK=0` and a throttled key.

### Setup option A — Use exhausted Groq key

- Set `GROQ_API_KEY` to a key that has hit its daily token quota (RPD/TPD exceeded)
- Ensure `GEMINI_API_KEY` is set and valid as fallback
- `GROQ_STRICT_PRIMARY=0` (default)

### Setup option B — Simulate in staging

- Temporarily set `GROQ_MODEL` to a non-existent model name to force 4xx
- `GROQ_DISABLE_GEMINI_FALLBACK=0`

### Steps

| # | Action | Expected |
|---|--------|----------|
| 1 | Trigger Gmail sync | |
| 2 | Check `GET /sync/history` for the pipeline run | |
| 3 | Inspect LangSmith trace (if `LANGSMITH_TRACING=true`) | run shows fallback model used |
| 4 | `GET /tasks?source=gmail` | tasks extracted despite primary failure |
| 5 | Check observability Redis: `obs:langsmith:ingest:counts` | `retry_exhausted` count increments on repeated 429s |

### Pass criteria

- [ ] Tasks extracted even when primary model fails
- [ ] `provenance.model` in pipeline run trace reflects fallback model name
- [ ] If ALL providers exhausted: pipeline run marked `status="failed"`, no crash
- [ ] After recovering primary key: next sync uses primary again (no sticky fallback state)

---

## Common Assertions (all flows)

After each pipeline run:

```bash
# No zombie sync locks
redis-cli keys "sync:lock:*"       # should be empty after job completes

# Progress keys cleaned up
redis-cli keys "sync:progress:*"   # should be empty after job completes

# No unhandled errors in worker logs
docker compose logs agent | grep -i "unhandled\|traceback\|exception" | tail -20
```

---

## Running Flow 1 Automatically

```bash
# Requires E2E_BASE_URL, E2E_JWT_TOKEN in env or .env.e2e
python scripts/e2e_gmail_sync.py

# Verbose (show task list)
python scripts/e2e_gmail_sync.py --verbose

# Fail if no tasks extracted (strict mode for CI)
python scripts/e2e_gmail_sync.py --require-tasks
```

See `scripts/e2e_gmail_sync.py` for implementation.
