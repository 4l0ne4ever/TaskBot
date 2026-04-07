# TaskBot

**TaskBot** is an assistant that turns scattered work content (Gmail, Google Drive, uploaded files) into **structured tasks**: title, assignee, deadline, and priority. It **normalizes** dates, **detects conflicts** across sources, and **stores** everything so users can confirm or edit tasks in a dashboard.

## Problem and value

- Deadlines and action items are buried in email and documents, which makes a single view hard.
- TaskBot **reads connected sources**, runs an AI pipeline, writes to **PostgreSQL**, and surfaces data in **Next.js**; the pipeline can **sync calendar** events (Google Calendar via MCP) where configured.

## Main capabilities

- **Scheduled sync** for Gmail and Drive (scheduler + Redis queue); users can **trigger sync manually**.
- **Multi-stage extraction** (LangGraph): parse content → extract tasks → normalize → validate / conflicts → persist → calendar notifications when applicable.
- **Conflict detection** (e.g. different deadlines or assignees for the same deliverable) and a UI to **resolve** (pick source A/B or dismiss).
- **Dedupe / task updates** for the same thread or file (dedupe group + fuzzy title).
- **File upload** (PDF/DOCX) to S3 and through the same pipeline.
- **Repeatable evaluation**: labeled dataset, rule / single-LLM / full-pipeline baselines, F1-style metrics, and Markdown reports.

## Technology (summary)

| Layer | Stack |
|-------|--------|
| UI | Next.js 14, Tailwind |
| API | FastAPI, Pydantic v2, JWT after Google OAuth |
| AI | Groq (Llama 3.3 70B primary, 8B fallback on rate limits), LangGraph |
| Data | PostgreSQL (Alembic), Redis (queue, job store, cache) |
| Google | MCP over HTTP (hosted Gmail/Calendar; Drive via in-repo `drive-mcp-server`) |
| Deploy | Docker Compose (Postgres, Redis, MCP Drive, backend, agent, frontend) |

## Architecture (blocks)

```
[ Next.js ] ──REST──► [ FastAPI: auth, tasks, sync, settings, upload ]
                              │
                              ▼
                        [ Redis queue ]
                              │
                              ▼
[ Agent: APScheduler + LangGraph ] ──MCP──► Gmail / Drive / Calendar
                              │
                              ▼
                        [ PostgreSQL ]
```

Flows, table schema, and design choices: [`docs/dev.md`](docs/dev.md).

## Repository layout

| Path | Role |
|------|------|
| `backend/` | API, auth, migrations |
| `agent/` | Worker, MCP clients, LangGraph pipeline |
| `drive-mcp-server/` | HTTP MCP bridge for Google Drive |
| `frontend/` | User dashboard |
| `tests/eval/` | Dataset, metrics, baselines, report outputs |
| `docs/` | Technical docs, tracking, run guide, demo flow |

## Documentation

| Doc | Purpose |
|-----|---------|
| **[`docs/run-guide.md`](docs/run-guide.md)** | **How to run** the product end-to-end (Docker stack, troubleshooting, optional host dev, tests, eval) |
| [`docs/demo-flow.md`](docs/demo-flow.md) | Demo script with URLs / `curl` per step |
| [`docs/dev.md`](docs/dev.md) | System design, flows, and schema |
| [`docs/tracking.md`](docs/tracking.md) | Phase checklist and progress |
| [`docs/setup-cloud.md`](docs/setup-cloud.md) | Cloud, OAuth, AWS |
| [`.env.example`](.env.example) | Environment variables (never commit secrets) |

## License / thesis

Use and cite according to your institution’s rules; this repository supports a thesis / capstone project for TaskBot.
