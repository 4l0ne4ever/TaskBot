# Refactor Plan — DEFERRED (2026-05-29)

**Status:** Audit done, plan written, execution **deferred** to focus on
deadline-bug verification and thesis writing. Resume only after:
1. Deadline-extraction root cause confirmed (provider-fallback verification).
2. Thesis Chương 4 draft is far enough along that the package diagram is
   stable — refactor first would require re-drawing.

This file is in `tmp/` (not gitignored by default — feel free to commit
or `rm` when no longer useful).

---

## Bước 1 — Audit Findings (baseline)

**Test baseline (line in the sand):** 462 passing
— 389 agent unit + 4 agent e2e + 69 backend. Must not drop.

**Code smells:** 0 TODO/FIXME/HACK, 0 debug prints. Codebase is **structurally
bloated** (big files, complex functions), not stylistically dirty.

**Top files by size + complexity (rank E-F = critical):**

| File | LOC | Worst function | CC | Notes |
|---|---|---|---|---|
| `agent/app/scheduler/queue_consumer.py` | **1099** | `_parse_gmail_message` / `_process_drive_job` / `_process_gmail_job` | E (35/32/31) | Skill said 580 — nearly doubled. **Priority 1.** |
| `agent/app/pipeline/llm.py` | 794 | `call_llm` | C (16) | Provider chain — complexity is the point. **Don't touch.** |
| `agent/app/pipeline/temporal_resolve.py` | 780 | `enrich_deadline_v2_with_symbolic_iso` | **F (57)** | Verified clean via pinned measurement. **Don't touch — thesis risk.** |
| `agent/app/services/observability.py` | 587 | — | A | Not chaotic, just large |
| `agent/app/pipeline/nodes/validate_tasks.py` | 579 | `validate_tasks` | E (36) | 4 conflict detectors inside — splittable |
| `frontend/.../sync/page.tsx` | **654** | 5 components in 1 file | — | Frontend single-file anti-pattern |
| `frontend/.../conflicts/page.tsx` | **613** | same | — | same |
| `frontend/.../calendar/page.tsx` | **539** | same | — | same |
| `agent/app/services/assignee_resolver.py` | 368 | `resolve` | C (14) | OK, cohesive class |
| `agent/app/services/save_tasks_service.py` | 343 | — | OK | |
| `agent/app/pipeline/nodes/extract_tasks.py` | 334 | — | C (15-17) | Cohesive |
| `agent/app/pipeline/nodes/normalize_tasks.py` | 316 | `_coerce_deadline_v2` | E (34) | Inherent (Postel coercion). Rename only. |
| `agent/app/services/entity_extractor.py` | 305 | — | OK | |
| `backend/app/api/observability.py` | 394 | — | OK | Could split sub-routers (defer) |
| `backend/app/api/tasks.py` | 386 | — | OK | Recently touched (pagination) |

**Incoming deps to the worst file:** `queue_consumer.py` is imported only by
`worker.py` (entry point) + 2 unit tests reaching internal helpers
(`_find_existing_source_doc`, `_extract_drive_raw_content`). Public surface
to preserve is **tiny → safe to split.**

---

## Bước 2 — Refactor Plan (staged by risk)

### Stage A — Trivial wins (low risk, ~30 min, no behavior change)

| # | Change | Files | Risk | Verify |
|---|---|---|---|---|
| A1 | Rename `normalize_tasks.py` → `schema_validate_tasks.py` (skill Priority 2 — the node never normalizes, only validates schema; confusing name) | 1 file + 3 imports | very low | full gate |
| A2 | CORS origin → `settings.frontend_url` (skill Priority 3) | `backend/app/main.py` + `backend/app/config.py` + `.env.example` | very low | backend tests + manual curl |
| A3 | `_run_async_save` asyncio pattern (skill Priority 5) | `agent/app/services/save_tasks_service.py` | low | full gate |

### Stage B — Frontend page split (medium-low risk, ~90 min, biggest readability win)

The 3 monster page files each bundle 4–5 sub-components inline. Pure
structural extraction — no logic change, no API change. Frontend has no
unit-test coverage so the verify is `npm run build` + manual smoke.

| # | Page (LOC) | Split into | Risk |
|---|---|---|---|
| B1 | `sync/page.tsx` (654) | `components/sync/` — `StepTracker`, `ResultBanner`, `SyncProgress`, `StatusBadge` extracted; page shrinks to ~200 LOC | low |
| B2 | `conflicts/page.tsx` (613) | `components/conflicts/` — similar split | low |
| B3 | `calendar/page.tsx` (539) | `components/calendar/` — similar split | low |
| B4 | (optional) shared bits → `components/ui/` | reuse `StatusBadge`-like patterns | low |

### Stage C — Backend hotspot split (medium risk, ~2–3 h, biggest maintainability win)

| # | Change | Risk | Verify |
|---|---|---|---|
| C1 | `queue_consumer.py` split per skill blueprint: `processors/gmail_processor.py`, `processors/drive_processor.py`, `processors/pressure_manager.py`, `processors/redis_io.py`, `queue_consumer.py` shrinks to orchestrator (~200 LOC). Public `consume_pipeline_jobs` + the 2 imported internals (`_find_existing_source_doc`, `_extract_drive_raw_content`) keep their import paths via re-export. | medium | per-extract test, then full gate, then `docker restart taskbot-agent` smoke |
| C2 | `validate_tasks.py` — extract 4 conflict detectors (`_detect_intra_batch_conflicts`, `_detect_multi_source_conflicts`, `_classify_conflict`, `_build_conflicts_for_task`) → `agent/app/pipeline/nodes/conflict_detectors.py`. `validate_tasks.py` keeps the main node + calibration/band logic. Hero E2E covers this path. | medium | hero E2E + full gate |

### Explicitly DEFERRED (won't touch this session)

| File | Reason |
|---|---|
| `temporal_resolve.py` (780, F-57) | Verified clean via pinned measurement; semantic refactor risks the thesis-grade finding. Rule 6 + memory `project-provider-fallback-root-cause` both warn against. |
| `llm.py` (794) | Provider chain complexity is intentional and was the entire diagnostic insight. Don't disturb. |
| `observability.py` (587 agent / 394 backend) | Large but cohesive; no chaos pain. |
| Frontend Dockerfile multi-stage | Not a "read/maintain" issue — dev workflow concern. |
| Backend API splits (tasks/conflicts/observability) | Each is one router with cohesive endpoints; cost > benefit. |

### Verify gate (run between every stage)

```bash
pytest agent/tests/unit/ -q                              # 389 must pass
pytest agent/tests/e2e/ -q                               # 4 must pass
DATABASE_URL='...:55432/...' pytest backend/tests/ -q    # 69 must pass
radon cc agent/app -s --min C                            # complexity must not increase
grep -rn "from app.scheduler.queue_consumer" agent      # no leaked internal paths
```

### Working method

- One stage per "go-ahead", verify gate green before starting the next.
- User commits (memory `feedback_user_commits_only`).
- If any stage's verify gate fails, stop and report — no patching to force green.

---

## Recommendation when resumed

Resume with **Stage A** (3 trivial wins, ~30 min, full gate green at the end).
Then re-evaluate B/C based on remaining thesis time. Skip C entirely if the
package diagram in Chương 4 is already drawn around the current shape — refactor
would force re-drawing.
