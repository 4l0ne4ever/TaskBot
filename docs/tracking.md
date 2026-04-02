# TaskBot — Project Plan & Todolist

> Cập nhật trạng thái: `[ ]` todo / `[x]` done / `[-]` in progress / `[~]` skipped

---

## Phase 0 — Setup & Foundation (Tuần 1–2)

### 0.1. Project setup

- [x] Khởi tạo repo, cấu trúc thư mục
- [x] Setup AWS-native services (postgres, redis, backend-api, agent-worker, frontend)
- [x] Tạo `.env.example` với tất cả biến cần thiết
- [x] Setup Alembic migrations

### 0.2. Database

- [x] Tạo migration: `users`
- [x] Tạo migration: `sync_states`
- [x] Tạo migration: `source_documents`
- [x] Tạo migration: `pipeline_runs`
- [x] Tạo migration: `tasks`
- [x] Tạo migration: `conflicts`
- [x] Thêm indexes quan trọng

### 0.3. Google OAuth

- [~] Setup Google Cloud Project, enable APIs (Gmail, Drive, Calendar) (manual external step)
- [x] Implement `/auth/google` redirect
- [x] Implement `/auth/callback` — exchange code → token
- [x] Lưu token encrypted vào DB
- [x] Implement `/auth/me`, `/auth/logout`
- [~] Test OAuth flow end-to-end (thực hiện sau khi có Google credentials thật)

### 0.4. Dataset chuẩn bị (song song)

- [~] Viết rubric gán nhãn (deadline, assignee, task title) (defer sang Phase 3 Evaluation)
- [~] Tạo 100 mẫu email giả lập (50 EN + 50 VI) (defer sang Phase 3 Evaluation)
- [~] Tạo 100 mẫu tài liệu giả lập (PDF/DOCX) (defer sang Phase 3 Evaluation)
- [~] Gán nhãn 200 mẫu theo rubric (defer sang Phase 3 Evaluation)
- [~] Spot-check 15–20% bởi người thứ hai (defer sang Phase 3 Evaluation)
- [~] Export sang format đánh giá (JSON) (defer sang Phase 3 Evaluation)

---

## Phase 1 — MCP Integration & Ingestion (Tuần 3–5)

### 1.1. File parsing (`agent-module`)

- [x] Implement email HTML → plain text parser
- [x] Implement PDF → text (PyMuPDF)
- [x] Implement DOCX → text (python-docx)
- [x] Implement content_hash generation (SHA256)
- [x] Unit test: `test_parser.py`

### 1.2. Gmail MCP (`agent-module`)

- [x] Kết nối Gmail MCP server
- [x] Implement `list_messages` call với filter (after timestamp, INBOX label)
- [x] Implement `get_message` call — lấy subject/sender/body
- [x] Implement `get_attachment` call
- [x] Implement historyId tracking (dedup)
- [~] Test: pull 10 email thật từ Gmail test account (đợi credentials/test account thật)

### 1.3. Google Drive MCP (`agent-module`)

- [x] Kết nối Drive MCP server
- [x] Implement `list_files` với filter (modifiedTime, mimeType)
- [x] Implement `list_shared_files`
- [x] Implement `get_file_content`
- [x] Implement pageToken tracking (dedup)
- [~] Test: pull files thật từ Drive test account (đợi credentials/test account thật)

### 1.4. File Upload API (`backend-api` + queue to `agent-module`)

- [x] Implement `POST /upload` endpoint
- [x] Lưu file lên S3 với prefix `{user_id}/`
- [x] Trigger pipeline ngay sau upload
- [x] Implement `GET /upload/:id/status`

### 1.5. Sync Scheduler (MVP) (`agent-module`)

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

- [ ] Kết nối Google Calendar MCP
- [ ] Implement `create_event` call
- [ ] Update tasks.calendar_event_id
- [ ] Implement in-app reminder (tasks không có deadline)
- [ ] Handle notification fail gracefully

### 2.8. Pipeline integration test

- [ ] Test full pipeline với mock LLM + mock MCP
- [ ] Test pipeline với Gmail email thật (1–2 account test)
- [ ] Test pipeline với Drive file thật
- [ ] Test pipeline với file upload

### 2.9. Tự động cập nhật task khi có thay đổi (deadline/assignee)

- [ ] Logic phát hiện “cùng task” giữa các lần sync (dedup + fuzzy match theo title/thread)
- [ ] Khi phát hiện deadline/assignee thay đổi → update DB task tương ứng thay vì tạo mới
- [ ] Nếu task đã có `calendar_event_id` → update event (hoặc delete+recreate theo ràng buộc API)
- [ ] Đồng bộ `conflicts` và trạng thái resolution khi có bản cập nhật mới
- [ ] Lưu audit/history cho lần cập nhật gần nhất (task revision metadata)
- [ ] Test scenario: email ban đầu deadline = A, email sau cập nhật deadline = B → chỉ 1 task và calendar được cập nhật

---

## Phase 3 — Evaluation (Tuần 9–10)

### 3.1. Baseline 1: Rule-based

- [ ] Implement regex/heuristic extraction
- [ ] Chạy trên toàn bộ dataset có nhãn
- [ ] Tính F1 per field

### 3.2. Baseline 2: Single LLM

- [ ] Implement single-call LLM extraction (không pipeline)
- [ ] Chạy trên toàn bộ dataset có nhãn
- [ ] Tính F1 per field

### 3.3. Pipeline evaluation

- [ ] Chạy multi-stage pipeline trên toàn bộ dataset có nhãn
- [ ] Tính F1 per field (title, deadline, assignee)
- [ ] Tính deadline exact match + near match
- [ ] Tính conflict detection F1

### 3.4. Phân tích kết quả

- [ ] Bảng so sánh 3 phương pháp
- [ ] Phân tích lỗi theo loại (deadline mơ hồ, tên viết tắt, v.v.)
- [ ] So sánh deadline conflict vs assignee conflict F1
- [ ] Viết chương đánh giá cho báo cáo

---

## Phase 4 — Backend API hoàn thiện (Tuần 11)

- [ ] `GET /tasks` với filters (status, source, deadline range)
- [ ] `GET /tasks/:id`
- [ ] `PATCH /tasks/:id` — confirm, dismiss, edit
- [ ] `DELETE /tasks/:id` + xóa calendar event
- [ ] `GET /tasks/conflicts`
- [ ] `PATCH /tasks/conflicts/:id` — resolve
- [ ] `GET /sync/status`
- [ ] `POST /sync/trigger`
- [ ] `GET /sync/history`
- [ ] `GET /settings`, `PATCH /settings`
- [ ] `POST /settings/disconnect` — revoke token
- [ ] Rate limiting (60 req/min per user)
- [ ] API tests: `test_api.py`

---

## Phase 5 — Frontend (Tuần 12)

- [ ] Setup Next.js, TailwindCSS, auth context
- [ ] Login page — Google OAuth button
- [ ] Task list page:
  - [ ] Table/list view với filter + sort
  - [ ] Missing field badge
  - [ ] Conflict indicator badge
  - [ ] Inline confirm/dismiss actions
- [ ] Task detail page — full info + edit deadline
- [ ] Conflicts page — side-by-side view + resolve buttons
- [ ] Sync status page — last sync, next sync, manual trigger
- [ ] Settings page — interval config, notifications toggle, disconnect
- [ ] Upload UI — drag & drop, status indicator
- [ ] Real-time sync status indicator (polling /sync/status)

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

- Hoàn thành Phase 0.1 (project setup, AWS-native service plan, `.env.example`, Alembic setup).
- Cập nhật kiến trúc: không dùng Docker, tách riêng `backend-api` và `agent-module`.
- Hoàn thành Phase 0.2 (base DB schema + migration + indexes).
- Hoàn thành phần code chính của Phase 0.3 (`/auth/google`, `/auth/callback`, token encryption, `/auth/me`, `/auth/logout`).
- Còn lại cần làm thủ công/kiểm chứng: cấu hình Google Cloud OAuth và test E2E OAuth flow.
- Đã xoá `docker-compose.yml`, chuẩn hoá triển khai sang AWS-native (`systemd` + `PM2` + `Nginx`).
- Đồng bộ structure thực tế: tách `backend-api/` (API + DB) và `agent-module/` (scheduler + MCP + pipeline).
- Chốt Phase 0 để bắt đầu Phase 1, các mục manual/deferred được đánh dấu `[~]`.
- Áp dụng rule `env`: thêm config module tập trung cho `backend-api` và `agent-module`, giảm hardcoded config trong source.
- Thêm tài liệu setup cloud tại `docs/setup-cloud.md` (GCP OAuth + AWS IAM Access Key + EC2/S3 checklist).
- Hoàn thành Phase 1.1 (`agent-module`): parser HTML/PDF/DOCX, SHA256 content hash, unit test `test_parser.py` (4 passed).
- Hoàn thành Phase 1.2 (`agent-module`): Gmail MCP client (`list_messages`, `get_message`, `get_attachment`) + historyId tracking qua Redis + unit tests (3 passed).
- Hoàn thành Phase 1.3 (`agent-module`): Drive MCP client (`list_files`, `list_shared_files`, `get_file_content`) + pageToken tracking qua Redis + unit tests (3 passed).

### Tuần 2

- Hoàn thành Phase 1.4 (`backend-api`): `POST /upload`, upload S3 theo prefix `{user_id}/`, queue trigger sang `agent-module`, và `GET /upload/{id}/status`.
- Hoàn thành test Phase 1.4: unit test upload service (`5 passed`), xác nhận flow hash/key/S3 call/validation.
- Hoàn thành Phase 1.5 (`agent-module`): scheduler polling jobs Gmail/Drive + chống overlap bằng Redis lock.
- Hoàn thành test Phase 1.5: unit test scheduler + sync lock/release (`4 passed`), không có linter errors ở các file mới chỉnh.

### Tuần 3

- Hoàn thành Phase 2.1 (`agent-module`): thêm `PipelineState`, dựng `StateGraph`, wiring các nodes và edge conditions (short-circuit khi parse fail / empty extraction).
- Hoàn thành test Phase 2.1: thêm unit test `test_pipeline_graph.py` để verify flow edges, chạy kèm parser tests (`6 passed`).
- Hoàn thành Phase 2.2 (`agent-module`): `parse_input` hỗ trợ metadata extraction, chunking text dài, và fail-safe output (`should_stop`, `errors`, `chunks`).
- Hoàn thành test Phase 2.2: thêm `test_parse_input_node.py` và verify cùng graph tests (`5 passed`).
- Hoàn thành Phase 2.3 (`agent-module`): thêm prompt extraction, LLM wrapper Groq (Llama 3.3 70B), parse/validate JSON extraction, retry tối đa 3 lần, merge kết quả từ chunks.
- Hoàn thành test Phase 2.3: thêm `test_extract_tasks_node.py` (mock LLM), regression graph tests, và full suite (`22 passed`).
- Hoàn thành Phase 2.4 (`agent-module`): thêm normalization prompt, triển khai `normalize_tasks` theo hướng tối ưu (batch 1 LLM call/document + retry + fallback chuẩn hóa để tránh fail pipeline).
- Hoàn thành test Phase 2.4: thêm `test_normalize_tasks_node.py` (LLM success + fallback path), full suite pass (`24 passed`).
- Hoàn thành Phase 2.5 (`agent-module`): `validate_tasks` có missing field check, fuzzy title matching với existing tasks, conflict prompt + parse/validate response, giới hạn số lần conflict check để tối ưu chi phí.
- Hoàn thành test Phase 2.5: thêm `test_validate_tasks_node.py`, chạy regression + full suite (`27 passed`).
- Hoàn thành Phase 2.6 (`agent-module`): thêm DB layer + models (mirror schema), `save_tasks` persist tasks/conflicts, dedup `content_hash` cross-document, cập nhật `pipeline_runs` + `source_documents`, transaction rollback qua `session.begin()`; node gọi `save_tasks_sync` (async + thread fallback khi có event loop).
- Hoàn thành test Phase 2.6: `test_save_tasks_node.py`, mock `save_tasks_sync` trong graph tests để tránh DB thật, full suite (`28 passed`).

_(tiếp tục...)_
