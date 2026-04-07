# TaskBot — Project Plan & Todolist

> Cập nhật trạng thái: `[ ]` todo / `[x]` done / `[-]` in progress / `[~]` skipped

---

## Phase 0 — Setup & Foundation (Tuần 1–2)

### 0.1. Project setup

- [x] Khởi tạo repo, cấu trúc thư mục
- [x] **Docker Compose (plan chính):** `docker-compose.yml` — Postgres, Redis, **mcp-drive** (`drive-mcp-server/`), backend, agent, frontend; Dockerfiles + `backend/docker-entrypoint.sh`; `.dockerignore`
- [x] Scripts: `./scripts/docker_infra.sh` (full stack / chỉ DB), `scripts/deploy_stack.sh` (EC2 Docker)
- [x] Legacy (tuỳ chọn): `deploy.sh` — EC2 không Docker (venv + systemd + PM2)
- [x] Tạo `.env.example` với tất cả biến cần thiết (kèm ghi chú Compose override)
- [x] Setup Alembic migrations (+ driver sync `psycopg2-binary` cho migration URL)

### 0.2. Database

- [x] Tạo migration: `users`
- [x] Tạo migration: `sync_states`
- [x] Tạo migration: `source_documents`
- [x] Tạo migration: `pipeline_runs`
- [x] Tạo migration: `tasks`
- [x] Tạo migration: `conflicts`
- [x] Thêm indexes quan trọng

### 0.3. Google OAuth

- [x] Setup Clerk project + publishable/secret keys
- [~] Setup Google Cloud Project, enable APIs (Gmail, Drive, Calendar) (manual external step)
- [x] Implement `/auth/google` redirect
- [x] Implement `/auth/callback` — exchange code → token
- [x] Lưu token encrypted vào DB
- [x] Implement `/auth/me`, `/auth/logout`
- [x] Automated test auth API flow (mock token exchange + mocked DB path)
- [~] Test OAuth flow end-to-end (thực hiện sau khi có Google credentials thật)

### 0.4. Dataset chuẩn bị (song song)

- [x] Viết rubric gán nhãn (deadline, assignee, task title) — `.cursor/skills/dataset-labeling/SKILL.md`
- [x] Tạo 250 mẫu (17 categories incl 7 edge cases, ~70% VI / ~30% EN) qua `tests/eval/generate_dataset.py` (seed=42, reproducible)
- [x] Gán nhãn 250 mẫu theo rubric (auto-labeled by generator with rubric rules)
- [~] Spot-check 15–20% bởi người thứ hai (cần manual review)
- [x] Export sang format đánh giá (JSON) — `tests/eval/labeled_dataset.json` (250 samples, 6826 lines)

---

## Phase 1 — MCP Integration & Ingestion (Tuần 3–5)

### 1.1. File parsing (`agent`)

- [x] Implement email HTML → plain text parser
- [x] Implement PDF → text (PyMuPDF)
- [x] Implement DOCX → text (python-docx)
- [x] Implement content_hash generation (SHA256)
- [x] Unit test: `test_parser.py`

### 1.2. Gmail MCP (`agent`)

- [x] Kết nối Gmail MCP server
- [x] Implement `list_messages` call với filter (after timestamp, INBOX label)
- [x] Implement `get_message` call — lấy subject/sender/body
- [x] Implement `get_attachment` call
- [x] Implement historyId tracking (dedup)
- [~] Test: pull email thật — chạy `python scripts/mcp_real_account_check.py` với `E2E_GOOGLE_ACCESS_TOKEN` (+ tùy chọn `E2E_EXPECT_GOOGLE_EMAIL`); pipeline E2E vẫn mục 2.8

### 1.3. Google Drive MCP (`agent`)

- [x] Kết nối Drive MCP server
- [x] Implement `list_files` với filter (modifiedTime, mimeType)
- [x] Implement `list_shared_files`
- [x] Implement `get_file_content`
- [x] Implement pageToken tracking (dedup)
- [~] Test: Drive thật — cùng script; thêm `--with-drive-download` để gọi `get_file_content` (PDF); Google-native files export PDF ở `drive-mcp-server`

### 1.4. File Upload API (`backend` + queue to `agent`)

- [x] Implement `POST /upload` endpoint
- [x] Lưu file lên S3 với prefix `{user_id}/`
- [x] Trigger pipeline ngay sau upload
- [x] Implement `GET /upload/:id/status`

### 1.5. Sync Scheduler (MVP) (`agent`)

- [x] Setup APScheduler với Redis job store
- [x] Implement Gmail polling job
- [x] Implement Drive polling job
- [x] Implement overlap prevention (check sync_states.status)
- [x] Test: scheduler chạy đúng chu kỳ, không overlap

---

## Phase 2 — AI Pipeline (Tuần 6–8)

### 2.1. LangGraph setup

- [x] Define `PipelineState` TypedDict
- [x] Setup LangGraph `StateGraph`
- [x] Implement edge conditions

### 2.2. Node: parse_input

- [x] Integrate file parsers vào node
- [x] Implement chunking cho text > 8000 tokens
- [x] Extract metadata (sender, sent_at, subject)
- [x] Handle should_stop khi parse fail

### 2.3. Node: extract_tasks

- [x] Viết Extraction prompt (EN + VI)
- [x] Implement Groq (Llama 3.3 70B) call
- [x] Parse JSON response → extracted_tasks[]
- [x] Implement retry 3 lần
- [x] Unit test với mock LLM

### 2.4. Node: normalize_tasks

- [x] Viết Normalization prompt
- [x] Implement deadline → ISO 8601 (dùng sent_at làm reference)
- [x] Implement assignee → canonical name
- [x] Implement priority normalization
- [x] Unit test: `test_normalization.py`

### 2.5. Node: validate_tasks

- [x] Implement missing field check (rule-based)
- [x] Implement conflict detection:
  - [x] Lấy existing tasks với fuzzy title match (tạm qua pipeline state, sẵn điểm nối DB adapter)
  - [x] Viết Conflict detection prompt
  - [x] Parse conflict response
- [x] Unit test: `test_conflict_detection.py`

### 2.6. Node: save_tasks

- [x] Implement dedup check (content_hash)
- [x] Insert tasks vào DB
- [x] Insert conflicts vào DB
- [x] Update pipeline_runs record
- [x] Rollback on error

### 2.7. Node: dispatch_notifications

- [x] Kết nối Google Calendar MCP
- [x] Implement `create_event` call
- [x] Update tasks.calendar_event_id
- [x] Implement in-app reminder (tasks không có deadline)
- [x] Handle notification fail gracefully

### 2.8. Pipeline integration test

- [x] Test full pipeline với mock LLM + mock MCP
- [ ] Test pipeline với Gmail email thật (sau khi MCP E2E script pass, chạy pipeline với token user)
- [ ] Test pipeline với Drive file thật (tương tự; `get_file_content` + parser)
- [x] Test pipeline với file upload (`test_pipeline_upload.py`: PDF bytes + HTML bytes, mock LLM)

### 2.9. Tự động cập nhật task khi có thay đổi (deadline/assignee)

- [x] Logic phát hiện “cùng task” giữa các lần sync — `source_documents.dedupe_group_id` (thread / Drive file) + fuzzy title ≥ 0.85; `metadata.dedupe_group_id` ghi xuống DB khi lưu
- [x] Khi khớp → UPDATE task (gán `source_doc_id` mới, `updated_at`) thay vì INSERT
- [x] Calendar — đã có sẵn: `dispatch_notifications` gọi `update_event` khi task giữ `calendar_event_id` (cùng id sau update)
- [x] Đồng bộ `conflicts` và trạng thái resolution khi có bản cập nhật mới — `save_tasks_service` auto-supersede old unresolved conflicts on task update
- [x] Lưu audit/history cho lần cập nhật gần nhất — `tasks.previous_revision` JSONB column; migration `0003`; snapshot trước khi update
- [ ] Test scenario E2E: email deadline A → B (chờ frontend/sync thật); hiện có unit `test_task_dedupe.py` + migration `0002_source_documents_dedupe_group_id`

---

## Phase 3 — Evaluation (Tuần 9–10)

### 3.1. Baseline 1: Rule-based

- [x] Implement regex/heuristic extraction — `tests/eval/baselines/rule_based.py`
- [x] Chạy trên dataset v2 (250 samples, 17 categories, 80 edge-tagged)
- [x] Tính F1 per field: Title=0.58, Assignee=0.64, Deadline Exact=0.63, Conflict=0.00
- [x] Report chi tiết: `tests/eval/results/rule_report.md` (per-sample + error heatmap)

### 3.2. Baseline 2: Single LLM

- [x] Implement single-call LLM extraction (không pipeline) — `tests/eval/baselines/single_llm.py`
- [x] Chạy trên dataset v2 (model: `llama-3.1-8b-instant`, 500K TPD) — Title F1=0.89, Assignee=0.89, DL Exact=0.48, Conflict=0.96; Fully correct 46.8%
- [x] Report chi tiết: `tests/eval/results/single_llm_report.md`

### 3.3. Pipeline evaluation

- [x] Fix parser compatibility cho model nhỏ (dict wrapper `{"tasks":[...]}` → unwrap trong `extract_tasks` + `normalize_tasks`)
- [x] Chạy multi-stage pipeline trên dataset v2 (model: `llama-3.1-8b-instant`) — Title F1=0.84 (R=0.97), Assignee=0.80, DL Exact=0.12, Conflict=0.00
- [x] Report chi tiết: `tests/eval/results/pipeline_report.md`

### 3.4. Phân tích kết quả

- [x] Bảng so sánh 3 phương pháp — `tests/eval/results/comparison_report.md`
- [x] Phân tích lỗi theo loại — error heatmap + error type distribution trong từng report
- [x] So sánh edge case vs core category performance (edge delta trong report)
- [ ] Viết chương đánh giá cho báo cáo

---

## Phase 4 — Backend API hoàn thiện (Tuần 11)

- [x] `GET /tasks` với filters (status, source, deadline range, sort, limit/offset)
- [x] `GET /tasks/:id`
- [x] `PATCH /tasks/:id` — confirm, dismiss, edit (title/assignee/deadline/priority/status)
- [x] `DELETE /tasks/:id` (trả calendar_event_id cho frontend xử lý nếu cần)
- [x] `GET /tasks/conflicts` (filter resolved, limit/offset)
- [x] `PATCH /tasks/conflicts/:id` — resolve (accept_a / accept_b / dismiss)
- [x] `GET /sync/status` — list sync_states per user
- [x] `POST /sync/trigger?source=gmail|drive` — enqueue manual sync job
- [x] `GET /sync/history` — pipeline_runs descending
- [x] `GET /settings`, `PATCH /settings` (gmail_interval, drive_interval, google_connected)
- [x] `POST /settings/disconnect` — revoke Google token (clear `oauth_token`)
- [x] Rate limiting (60 req/min per user, in-memory sliding window `RateLimitMiddleware`)
- [x] CORS middleware (localhost:3000)
- [x] Pydantic v2 schemas: `task.py`, `conflict.py`, `sync.py`, `settings.py`
- [x] API tests: `test_tasks_api.py` (7), `test_sync_api.py` (4), `test_settings_api.py` (5) — **total 25 backend tests pass**

---

## Phase 5 — Frontend (Tuần 12)

- [x] Setup Next.js 14, TailwindCSS, `AuthProvider` + `AppShell` (`app/(dashboard)/layout.tsx`)
- [x] Login page — Google OAuth qua backend `/auth/google`; redirect về `/auth/callback#access_token=…` (Clerk có thể thêm sau; `.env.example` ghi chú)
- [x] Task list page:
  - [x] Table/list view với filter (status, source) + sort (newest / deadline)
  - [x] Missing field badge
  - [x] Conflict indicator badge (từ `GET /tasks/conflicts?resolved=false`)
  - [x] Inline confirm/dismiss actions
- [x] Task detail page — full info + edit deadline (PATCH)
- [x] Conflicts page — side-by-side (2 tasks theo `task_ids`) + accept_a / accept_b / dismiss
- [x] Sync page — trạng thái từng source, history pipeline runs, manual trigger Gmail/Drive + polling 15s
- [x] Settings page — gmail/drive interval (PATCH), disconnect Google; ghi chú API chưa có notification toggle riêng
- [x] Upload UI — drag & drop PDF/DOCX, poll `/upload/{id}/status`
- [x] Sync status indicator trong header (poll `/sync/status` mỗi 30s)

**Backend hỗ trợ OAuth UX:** `GET /auth/callback` redirect tới `{FRONTEND_URL}/auth/callback#access_token=…`; test dùng `&as_json=true`. `TaskResponse` thêm `source_type` (join `source_documents`).

---

## Phase 6 — End-to-End Testing & Polish (Tuần 13)

- [ ] E2E test checklist (xem dev_documentation.md mục 12.3)
- [ ] Test với Gmail account thật (nhiều email types)
- [ ] Test với Drive thật (PDF, DOCX, shared files)
- [ ] Performance test: pipeline latency, sync latency
- [ ] Bug fixes từ E2E
- [ ] Security review: token exposure, rate limits, data isolation

---

## Phase 7 — Báo cáo & Bảo vệ (Tuần 14–16)

### Báo cáo

- [ ] Chương 1: Giới thiệu + bài toán
- [ ] Chương 2: Cơ sở lý thuyết (LLM extraction, NLP, MCP)
- [ ] Chương 3: Thiết kế hệ thống (architecture, pipeline, schema)
- [ ] Chương 4: Kết quả thực nghiệm (evaluation + bảng so sánh)
- [ ] Chương 5: Demo + kết luận + hướng phát triển
- [ ] Review và chỉnh sửa toàn bộ

### Bảo vệ

- [ ] Chuẩn bị slides (10–12 slides)
- [ ] Demo script (3–5 phút flow)
- [ ] Chuẩn bị trả lời câu hỏi hội đồng:
  - [ ] "Khác gì ChatGPT?"
  - [ ] "Multi-agent có cần thiết không?"
  - [ ] "Conflict detection chính xác bao nhiêu %?"
  - [ ] "Dataset tự tạo có bias không?"

---

## Backlog (nếu có thời gian)

- [ ] Slack integration qua MCP adapter
- [ ] Push notification qua webhook thay vì polling
- [ ] Role-based access control cho team use case
- [ ] Active learning: user confirm/reject → cải thiện prompt
- [ ] Email digest hàng ngày (tóm tắt tasks mới)
- [ ] Export tasks ra CSV/Notion

---

## Tracking Notes

> Ghi chú tiến độ hàng tuần ở đây

### Tuần 1

- Hoàn thành Phase 0.1 (project setup, Docker Compose full stack là mặc định; legacy EC2 systemd/PM2 qua `deploy.sh`).
- Kiến trúc: tách `backend` và `agent`; triển khai ưu tiên Docker Compose (local + EC2 có thể dùng `deploy_stack.sh`).
- Hoàn thành Phase 0.2 (base DB schema + migration + indexes).
- Hoàn thành phần code chính của Phase 0.3 (`/auth/google`, `/auth/callback`, token encryption, `/auth/me`, `/auth/logout`).
- Còn lại cần làm thủ công/kiểm chứng: cấu hình Google Cloud OAuth và test E2E OAuth flow.
- Đã chuyển lại plan: `docker-compose.yml` full stack; EC2 có thể Docker hoặc legacy `deploy.sh` + systemd/PM2 + Nginx.
- Đồng bộ structure thực tế: tách `backend/` (API + DB) và `agent/` (scheduler + MCP + pipeline).
- Chốt Phase 0 để bắt đầu Phase 1, các mục manual/deferred được đánh dấu `[~]`.
- Áp dụng rule `env`: thêm config module tập trung cho `backend` và `agent`, giảm hardcoded config trong source.
- Thêm tài liệu setup cloud tại `docs/setup-cloud.md` (GCP OAuth + AWS IAM Access Key + EC2/S3 checklist).
- Hoàn thành Phase 1.1 (`agent`): parser HTML/PDF/DOCX, SHA256 content hash, unit test `test_parser.py` (4 passed).
- Hoàn thành Phase 1.2 (`agent`): Gmail MCP client (`list_messages`, `get_message`, `get_attachment`) + historyId tracking qua Redis + unit tests (3 passed).
- Hoàn thành Phase 1.3 (`agent`): Drive MCP client (`list_files`, `list_shared_files`, `get_file_content`) + pageToken tracking qua Redis + unit tests (3 passed).

### Tuần 2

- Hoàn thành Phase 1.4 (`backend`): `POST /upload`, upload S3 theo prefix `{user_id}/`, queue trigger sang `agent`, và `GET /upload/{id}/status`.
- Hoàn thành test Phase 1.4: unit test upload service (`5 passed`), xác nhận flow hash/key/S3 call/validation.
- Hoàn thành Phase 1.5 (`agent`): scheduler polling jobs Gmail/Drive + chống overlap bằng Redis lock.
- Hoàn thành test Phase 1.5: unit test scheduler + sync lock/release (`4 passed`), không có linter errors ở các file mới chỉnh.

### Tuần 3

- Hoàn thành Phase 2.1 (`agent`): thêm `PipelineState`, dựng `StateGraph`, wiring các nodes và edge conditions (short-circuit khi parse fail / empty extraction).
- Hoàn thành test Phase 2.1: thêm unit test `test_pipeline_graph.py` để verify flow edges, chạy kèm parser tests (`6 passed`).
- Hoàn thành Phase 2.2 (`agent`): `parse_input` hỗ trợ metadata extraction, chunking text dài, và fail-safe output (`should_stop`, `errors`, `chunks`).
- Hoàn thành test Phase 2.2: thêm `test_parse_input_node.py` và verify cùng graph tests (`5 passed`).
- Hoàn thành Phase 2.3 (`agent`): thêm prompt extraction, LLM wrapper Groq (Llama 3.3 70B), parse/validate JSON extraction, retry tối đa 3 lần, merge kết quả từ chunks.
- Hoàn thành test Phase 2.3: thêm `test_extract_tasks_node.py` (mock LLM), regression graph tests, và full suite (`22 passed`).
- Hoàn thành Phase 2.4 (`agent`): thêm normalization prompt, triển khai `normalize_tasks` theo hướng tối ưu (batch 1 LLM call/document + retry + fallback chuẩn hóa để tránh fail pipeline).
- Hoàn thành test Phase 2.4: thêm `test_normalize_tasks_node.py` (LLM success + fallback path), full suite pass (`24 passed`).
- Hoàn thành Phase 2.5 (`agent`): `validate_tasks` có missing field check, fuzzy title matching với existing tasks, conflict prompt + parse/validate response, giới hạn số lần conflict check để tối ưu chi phí.
- Hoàn thành test Phase 2.5: thêm `test_validate_tasks_node.py`, chạy regression + full suite (`27 passed`).
- Hoàn thành Phase 2.6 (`agent`): thêm DB layer + models (mirror schema), `save_tasks` persist tasks/conflicts, dedup `content_hash` cross-document, cập nhật `pipeline_runs` + `source_documents`, transaction rollback qua `session.begin()`; node gọi `save_tasks_sync` (async + thread fallback khi có event loop).
- Hoàn thành test Phase 2.6: `test_save_tasks_node.py`, mock `save_tasks_sync` trong graph tests để tránh DB thật, full suite (`28 passed`).
- Đồng bộ naming toàn repo: dùng `backend/` và `agent/` (thay cho `backend-api`/`agent-module`), cập nhật script test/deploy/docs tương ứng.
- Đồng bộ LLM runtime sang Groq + Llama 3.3 70B: thay env/config/client (`GROQ_API_KEY`, `GROQ_MODEL`) và cập nhật dependency `groq`.
- Hoàn thành Phase 2.7 (`agent`): thêm `CalendarMCPClient`, triển khai `dispatch_notifications` (create/update calendar event, in-app reminder cho task không có deadline, fail-safe không crash pipeline).
- Hoàn thành test Phase 2.7: thêm `test_dispatch_notifications_node.py`, full suite pass (`29 passed`).
- Hoàn thành setup Clerk project (publishable/secret keys) và đồng bộ `.env` cho mô hình hybrid Clerk + Google OAuth.
- Ổn định config runtime: `backend` và `agent` settings cho phép ignore env keys không liên quan (`extra=ignore`) để tránh crash khi dùng `.env` chung; full suite vẫn pass (`29 passed`).
- Hoàn thành bổ sung test auth API Phase 0.3 tại `backend/tests/unit/test_auth_api.py` cho các route `/auth/google`, `/auth/callback`, `/auth/me`, `/auth/logout` (mock token exchange + mocked DB path).
- Hoàn thành mục đầu Phase 2.8: thêm test full pipeline mock tại `agent/tests/unit/test_pipeline_graph.py` (mock LLM + mock save/dispatch path).
- Bổ sung dependency `python-multipart` vào `requirements.txt` để tránh lỗi runtime khi import route upload; full suite hiện pass (`39 passed`: backend `9`, agent `30`).
- Docker Compose **full stack** (Postgres, Redis, backend, agent, frontend); `scripts/deploy_stack.sh`; cập nhật `dev.md`, `setup-cloud.md`, `proposal.md`, skill `local-dev-setup`. MCP: repo chỉ HTTP client; Drive MCP chạy riêng (cân nhắc `extra_hosts` / `host.docker.internal` nếu agent trong container gọi MCP trên host).

- Docker full stack + **`drive-mcp-server`**: HTTP MCP bridge Google Drive (service `mcp-drive`), agent `DRIVE_MCP_URL` override trong compose; `scripts/verify_stack.sh` smoke test; docs/skill MCP giải thích client vs server (hosted Gmail/Calendar vs in-repo Drive).

### Tuần 4

- Hoàn thành Phase 2.9 (core): `source_documents.dedupe_group_id` + migration `0002`; `save_tasks_service` update-in-place khi title match ≥ 0.85 cùng nhóm; `validate_tasks` load existing tasks từ DB; unit test `test_task_dedupe.py`; toàn suite agent **34 passed**.
- Hoàn thành Phase 4 (Backend API hoàn thiện): tất cả route tasks/conflicts/sync/settings đã implement; Pydantic v2 schemas; CORS + rate limiting middleware (60 req/min/user); **25 backend tests pass**, full suite **65 passed** (25 backend + 34 agent + 6 drive-mcp).
- Phase 2.9 bổ sung: conflict auto-supersede khi task được update; `parse_input` hỗ trợ HTML/TXT/MD upload; `tasks.previous_revision` JSONB audit trail (migration `0003`); `test_pipeline_upload.py` (2 tests); full suite **67 passed**.
- Hoàn thành Phase 0.4 v2 (Dataset): viết lại `generate_dataset.py` — **17 categories** (10 core + 7 edge case), **80 edge-tagged** samples, 250 tổng, VI/EN/mixed; `labeled_dataset.json`.
- Nâng cấp eval infra: `run_eval.py` output per-sample details + error analysis + auto-gen markdown report (`*_report.md`); `compare_results.py` output `comparison_report.md`.
- Hoàn thành Phase 3.1 v2 (Rule-based): Title F1=0.58, Assignee=0.64, Deadline Exact=0.63, Conflict=0.00; `rule_report.md` có error heatmap 17 categories.
- Phân tích Groq rate limits (dashboard: 429 burst → 340/min peak). Nguyên nhân: `llama-3.3-70b-versatile` chỉ có 100K TPD + 1000 RPD.
- Chuyển eval sang `llama-3.1-8b-instant` (500K TPD, 14400 RPD, 30 RPM). Cùng model cho cả 3 methods = so sánh công bằng.
- Fix parser compatibility: model nhỏ trả `{"tasks":[...]}` thay vì bare `[...]`; update `parse_extraction_response` + `_parse_normalization_response` unwrap dict.
- Hoàn thành Phase 3.2 + 3.3 (all eval runs):
  - `single_llm_70b.json` — 70b primary + 8b fallback: 82 calls 70b, 168 calls 8b
  - `pipeline.json` — 8b (70b TPD exhausted; pipeline cần ~750 LLM calls/250 samples)
  - `rule.json`, `single_llm.json` (pure 8b baseline)
- Hoàn thành Phase 3.4: `comparison_report.md` (4 methods side-by-side)
- Key findings (70b primary single_llm — best overall method):

  | Metric | Rule | Single LLM 70b | Single LLM 8b | Pipeline 8b |
  |--------|------|----------------|---------------|-------------|
  | Title F1 | 0.578 | **0.877** | 0.893 | 0.841 |
  | Assignee F1 | 0.635 | **0.901** | 0.888 | 0.796 |
  | DL Exact | 0.628 | **0.562** | 0.479 | 0.120 |
  | DL Near | 0.641 | **0.719** | 0.632 | 0.145 |
  | Conflict F1 | 0.000 | **0.943** | 0.960 | 0.000 |
  | Fully correct | 26.8% | **51.2%** | 46.8% | 13.2% |

  - 70b clearly better at deadline normalization (0.56 vs 0.48 exact) and assignee (0.90 vs 0.89)
  - Pipeline conflict F1=0 by design (inter-doc detection, eval has no existing_tasks); single LLM detects intra-doc conflicts
  - Edge cases: LLM methods perfect on forwarded/mixed_lang/nickname/priority; `edge_tricky_negative` = 0 for all
  - Implemented 70b primary + 8b fallback in `agent/app/pipeline/llm.py` for production use

- Audit & doc sync:
  - Updated `project-context/SKILL.md`: Groq/Llama (was Gemini), separated agent/backend structure, Clerk + OAuth auth
  - Updated `ai-agents/SKILL.md`: Groq SDK (was google-genai)
  - Fixed tracking.md: 17 categories (was 10)
  - All 61 unit tests pass (36 agent + 25 backend)

### Tuần 5

- Hoàn thành **Phase 5 (Frontend)**: Next.js App Router, Tailwind, `AuthProvider`, dashboard shell, pages tasks / task detail / conflicts / sync / settings / upload, `lib/api.ts` khớp backend, toast errors, polling sync indicator + sync page.
- Backend: OAuth callback redirect browser về `FRONTEND_URL/auth/callback#access_token=…` (`as_json=true` cho pytest); `TaskResponse.source_type` + enrich trong `tasks.py`.
- `.env.example`: `FRONTEND_URL`, `NEXT_PUBLIC_API_URL`.

_(tiếp tục...)_
