# TaskBot — Developer Documentation

> Tài liệu này dành cho team dev. Không bao gồm code — chỉ bao gồm thiết kế, luồng xử lý và quyết định kiến trúc đủ để implement.

---

## 1. Tổng quan hệ thống

### 1.1. Mô tả ngắn gọn

TaskBot là AI bot tự động đọc email và tài liệu từ Gmail/Google Drive, trích xuất thông tin công việc, chuẩn hóa, phát hiện mâu thuẫn, và tạo calendar event/reminder cho người dùng.

### 1.2. User flow tổng quát

```
User kết nối Google account (OAuth)
        ↓
Bot bắt đầu polling Gmail + Drive theo chu kỳ
        ↓
Khi có dữ liệu mới → chạy AI pipeline
        ↓
Tasks được lưu vào DB
        ↓
Calendar event được tạo tự động
        ↓
User xem và quản lý tasks trên UI
```

### 1.3. Các actor

| Actor                       | Mô tả                                                              |
| --------------------------- | ------------------------------------------------------------------ |
| **User**                    | Người dùng cuối — kết nối Google account, xem tasks, cấu hình sync |
| **Scheduler**               | Background job chạy polling định kỳ                                |
| **AI Pipeline**             | LangGraph graph xử lý một document/email                           |
| **MCP Servers**             | Gmail, Drive, Calendar — interface với Google APIs                 |
| **Notification Dispatcher** | Gửi calendar event sau khi pipeline xong                           |

---

## 2. Kiến trúc hệ thống

### 2.1. Component diagram

```
┌─────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                │
│   Task List │ Conflict View │ Sync Status │ Settings     │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────────┐
│                  Backend API (FastAPI)                   │
│  Auth Layer │ Task API │ Sync API │ Settings/Upload     │
└───────────────────────┬─────────────────────────────────┘
                        │ enqueue jobs / trigger run
┌───────────────────────▼─────────────────────────────────┐
│                      Redis Queue                         │
└───────────────────────┬─────────────────────────────────┘
                        │ dequeue
┌───────────────────────▼─────────────────────────────────┐
│         Agent Module (Worker + LangGraph Pipeline)       │
│ APScheduler + Ingestion → Extraction → Normalize →       │
│ Validation → Save → Notify                               │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
   ┌─────────────┐ ┌──────────┐ ┌──────────────┐
   │ MCP: Gmail  │ │MCP: Drive│ │MCP: Calendar │
   └──────┬──────┘ └────┬─────┘ └──────┬───────┘
          │             │              │
          └─────────────┴──────────────┘
                        │
                     Google APIs
```

### 2.2. Separation of concerns

| Layer        | Trách nhiệm                        | KHÔNG làm                                |
| ------------ | ---------------------------------- | ---------------------------------------- |
| Frontend     | Hiển thị, user input, cấu hình     | Business logic, gọi Google API trực tiếp |
| Backend API  | REST API, auth, settings, orchestration | Chạy trực tiếp pipeline AI           |
| Agent Module | Scheduler + AI pipeline execution  | Expose public API                        |
| MCP Servers  | Interface với Google APIs          | Business logic                           |
| PostgreSQL   | Lưu trữ bền vững                   | Cache, queue                             |
| Redis        | Queue, dedup, cache token          | Lưu trữ bền vững                         |

---

## 2.3. Project structure (thực tế)

```
taskExtractor/
├── backend-api/      # FastAPI API + auth + DB layer
├── agent-module/     # Scheduler + MCP clients + LangGraph pipeline
├── frontend/         # Next.js dashboard
└── docs/
```

---

## 3. Database Schema

### 3.1. Bảng chính

**`users`**

```
id              UUID, PK
email           TEXT, UNIQUE
google_id       TEXT, UNIQUE
oauth_token     TEXT (encrypted)         — access + refresh token
sync_config     JSONB                    — chu kỳ polling, folder filters
created_at      TIMESTAMP
last_active_at  TIMESTAMP
```

**`sync_states`**

```
id              UUID, PK
user_id         UUID, FK → users
source_type     ENUM(gmail, drive)
last_sync_at    TIMESTAMP
last_cursor     TEXT                     — Gmail historyId / Drive pageToken
status          ENUM(idle, running, error)
error_message   TEXT
```

**`source_documents`**

```
id              UUID, PK
user_id         UUID, FK → users
source_type     ENUM(gmail, drive, upload)
source_ref      TEXT                     — message_id / file_id / upload_id
content_hash    TEXT                     — SHA256 để dedup
raw_text        TEXT
processed_at    TIMESTAMP
pipeline_run_id UUID
```

**`tasks`**

```
id              UUID, PK
user_id         UUID, FK → users
source_doc_id   UUID, FK → source_documents
title           TEXT NOT NULL
assignee        TEXT
deadline        DATE
priority        ENUM(high, medium, low)
missing_fields  TEXT[]                   — ["assignee", "deadline"]
status          ENUM(pending, confirmed, dismissed)
calendar_event_id TEXT
notification_sent BOOLEAN DEFAULT FALSE
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

**`conflicts`**

```
id              UUID, PK
user_id         UUID, FK → users
conflict_type   ENUM(deadline_conflict, assignee_conflict)
description     TEXT
source_a_ref    TEXT
source_b_ref    TEXT
task_ids        UUID[]                   — các tasks liên quan
resolved        BOOLEAN DEFAULT FALSE
created_at      TIMESTAMP
```

**`pipeline_runs`**

```
id              UUID, PK
user_id         UUID, FK → users
source_doc_id   UUID, FK → source_documents
status          ENUM(running, completed, failed)
tasks_extracted INT DEFAULT 0
conflicts_found INT DEFAULT 0
started_at      TIMESTAMP
completed_at    TIMESTAMP
error_message   TEXT
```

### 3.2. Indexes quan trọng

```
tasks(user_id, deadline)          — query tasks theo deadline
tasks(user_id, status)            — filter by status
source_documents(content_hash)    — dedup check
sync_states(user_id, source_type) — lookup per user per source
conflicts(user_id, resolved)      — filter unresolved conflicts
```

---

## 4. LangGraph Pipeline

### 4.1. State schema

```python
# Toàn bộ state được truyền qua các nodes
PipelineState = {
    # Input (set khi khởi tạo)
    "user_id": str,
    "source_doc_id": str,
    "source_type": "gmail" | "drive" | "upload",
    "raw_content": str,              # text đã được parse từ email/file

    # After ingestion node
    "cleaned_text": str,
    "metadata": dict,                # sender, sent_at, subject, file_name...

    # After extraction node
    "extracted_tasks": list[dict],   # raw extraction, chưa normalize

    # After normalization node
    "normalized_tasks": list[dict],  # deadline → ISO, assignee → canonical

    # After validation node
    "validated_tasks": list[dict],   # + missing_fields, conflicts
    "conflicts": list[dict],

    # After save node
    "saved_task_ids": list[str],

    # After notify node
    "notifications_sent": list[dict],

    # Error handling
    "errors": list[str],
    "should_stop": bool,
}
```

### 4.2. Node definitions

```
Node 1 — parse_input
  Input:  raw_content (email HTML / PDF bytes / DOCX bytes)
  Output: cleaned_text (plain text), metadata
  Logic:  - Email: strip HTML, extract subject/sender/date
          - PDF: PyMuPDF text extraction
          - DOCX: python-docx text extraction
          - Chunking nếu text > 8000 tokens
  Fail:   set errors[], should_stop=True nếu không parse được

Node 2 — extract_tasks
  Input:  cleaned_text, metadata
  Output: extracted_tasks[]
  Logic:  Groq (Llama 3.3 70B) call với Extraction prompt
          Trả về list tasks: {title, assignee_raw, deadline_raw, priority_raw}
          Nếu text không có task nào → extracted_tasks = []
  Fail:   retry 3 lần, sau đó set errors[]

Node 3 — normalize_tasks
  Input:  extracted_tasks[], metadata.sent_at (để tính relative date)
  Output: normalized_tasks[]
  Logic:  Groq (Llama 3.3 70B) call với Normalization prompt
          deadline_raw → ISO 8601 date (dùng sent_at làm reference)
          assignee_raw → match với user list trong system
          priority_raw → high/medium/low/null
  Fail:   retry 3 lần; nếu fail → giữ nguyên raw value, flag warning

Node 4 — validate_tasks
  Input:  normalized_tasks[], source_doc_id, user_id
  Output: validated_tasks[] (+ missing_fields), conflicts[]
  Logic:
    Missing field check (rule-based, không cần LLM):
      - Nếu deadline = null → thêm "deadline" vào missing_fields
      - Nếu assignee = null → thêm "assignee" vào missing_fields

    Conflict check (query DB + LLM):
      - Lấy existing tasks cùng user có title tương tự (fuzzy match)
      - Nếu tìm thấy → gọi Groq (Llama 3.3 70B) để so sánh deadline/assignee
      - Nếu conflict → tạo conflict record
  Fail:   bỏ qua conflict check, vẫn lưu tasks

Node 5 — save_tasks
  Input:  validated_tasks[], conflicts[]
  Output: saved_task_ids[]
  Logic:
    - Insert vào bảng tasks
    - Insert vào bảng conflicts nếu có
    - Update pipeline_runs record
    - Dedup: check content_hash trước khi insert
    - Auto-update: nếu “cùng task” đã tồn tại và deadline/assignee thay đổi (vd email lùi deadline) → update record thay vì tạo mới; đồng bộ calendar_event nếu đã có
  Fail:   rollback, set errors[]

Node 6 — dispatch_notifications
  Input:  saved_task_ids[], validated_tasks[]
  Output: notifications_sent[]
  Logic:
    - Với mỗi task có deadline:
      → Gọi Calendar MCP để tạo event
      → Nếu task đã có `calendar_event_id` → update event theo deadline mới
      → Update tasks.calendar_event_id
      → Set tasks.notification_sent = true
    - Với tasks không có deadline:
      → Tạo in-app reminder (insert vào reminders table)
  Fail:   log error, không crash pipeline
```

### 4.3. Edge conditions

```
parse_input ──────────────────────────────────► extract_tasks
    │ should_stop=True                              │
    ▼                                              │ extracted_tasks=[]
  END (error)                                      ▼
                                              save_tasks (empty run)
                                                   │
extract_tasks ──────────────► normalize_tasks ──► validate_tasks
                                                   │
                                              save_tasks ──► dispatch_notifications ──► END
```

### 4.4. Prompt design principles

Mỗi node có prompt riêng, không gộp chung:

**Extraction prompt:**

- Chỉ yêu cầu trích xuất, không yêu cầu normalize
- Output format: JSON array, schema cố định
- Instruction: "Nếu không tìm thấy task, trả về mảng rỗng []"

**Normalization prompt:**

- Nhận extracted task + context (ngày email gửi, danh sách user)
- Chỉ làm normalize, không re-extract
- Instruction về cách xử lý từng loại deadline mơ hồ

**Conflict validation prompt:**

- Nhận task A (mới) + task B (existing từ DB)
- Chỉ trả về: conflict_type hoặc "no_conflict"
- Không làm gì khác

---

## 5. MCP Integration

### 5.1. Gmail MCP

**Scope cần thiết:** `gmail.readonly`, `gmail.labels`

**Các tool được dùng:**

| Tool             | Khi nào dùng                 | Input                                      | Output                             |
| ---------------- | ---------------------------- | ------------------------------------------ | ---------------------------------- |
| `list_messages`  | Polling — lấy messages mới   | `after: last_sync_timestamp, label: INBOX` | list message_ids                   |
| `get_message`    | Lấy content của từng message | `message_id`                               | subject, sender, body, attachments |
| `get_attachment` | Lấy file đính kèm            | `message_id, attachment_id`                | file bytes                         |

**Dedup strategy:** Lưu `historyId` của Gmail sau mỗi sync. Lần sau chỉ lấy messages có `historyId > last_historyId`.

### 5.2. Google Drive MCP

**Scope cần thiết:** `drive.readonly`

**Các tool được dùng:**

| Tool                | Khi nào dùng                | Input                                               | Output        |
| ------------------- | --------------------------- | --------------------------------------------------- | ------------- |
| `list_files`        | Polling — lấy files mới/sửa | `modifiedTime > last_sync, mimeType in [pdf, docx]` | list file_ids |
| `get_file_content`  | Đọc nội dung file           | `file_id`                                           | file bytes    |
| `list_shared_files` | Lấy files được share        | `sharedWithMe=true, modifiedTime > last_sync`       | list file_ids |

**Dedup strategy:** Lưu `pageToken` của Drive API. Kết hợp với `content_hash` để tránh process lại file không thay đổi.

### 5.3. Google Calendar MCP

**Scope cần thiết:** `calendar.events`

**Các tool được dùng:**

| Tool           | Khi nào dùng                       | Input                                 | Output        |
| -------------- | ---------------------------------- | ------------------------------------- | ------------- |
| `create_event` | Sau khi task có deadline được save | `title, date, description, reminders` | event_id      |
| `update_event` | Khi user confirm/edit task         | `event_id, new_data`                  | updated event |
| `delete_event` | Khi user dismiss task              | `event_id`                            | —             |

---

## 6. Sync Scheduler Design

### 6.1. Job flow

```
APScheduler trigger (15min / 30min)
        ↓
Lấy danh sách users có sync enabled
        ↓
Với mỗi user:
  Check sync_states — nếu status = "running" → skip (tránh overlap)
  Set status = "running"
        ↓
  Gọi MCP để lấy danh sách source IDs mới
        ↓
  Với mỗi source ID:
    Check content_hash trong DB → nếu đã có → skip
    Enqueue job vào Redis
        ↓
  Set status = "idle", update last_sync_at, last_cursor
        ↓
Worker lấy job từ Redis → chạy LangGraph pipeline
```

### 6.2. Concurrency rules

- Mỗi user chỉ có 1 sync job chạy tại một thời điểm (check sync_states.status)
- Mỗi source document được process đúng 1 lần (check content_hash)
- Max 3 pipeline workers song song (cấu hình được)
- Timeout mỗi pipeline job: 5 phút

### 6.3. Error handling

| Loại lỗi                  | Xử lý                                                  |
| ------------------------- | ------------------------------------------------------ |
| MCP call fail             | Retry 3 lần với exponential backoff, sau đó log + skip |
| LLM API fail              | Retry 3 lần, sau đó mark pipeline_run as failed        |
| Parse fail (file corrupt) | Mark source_document as parse_failed, skip             |
| DB write fail             | Rollback, retry 1 lần, sau đó alert                    |

---

## 7. API Endpoints

### 7.1. Auth

```
GET  /auth/google              — redirect đến Google OAuth
GET  /auth/callback            — nhận code, exchange token, tạo user session
POST /auth/logout              — revoke token, clear session
GET  /auth/me                  — thông tin user hiện tại
```

### 7.2. Tasks

```
GET  /tasks                    — list tasks của user (filter: status, deadline, source)
GET  /tasks/:id                — chi tiết một task
PATCH /tasks/:id               — update task (confirm, dismiss, edit deadline)
DELETE /tasks/:id              — xóa task + calendar event tương ứng

GET  /tasks/conflicts          — list unresolved conflicts
PATCH /tasks/conflicts/:id     — resolve conflict (chọn source nào đúng)
```

### 7.3. Sync

```
GET  /sync/status              — trạng thái sync hiện tại (last_sync, next_sync)
POST /sync/trigger             — trigger sync thủ công (không đợi scheduler)
GET  /sync/history             — lịch sử sync runs
```

### 7.4. Settings

```
GET  /settings                 — cấu hình sync hiện tại
PATCH /settings                — update: gmail_interval, drive_interval, folders, notifications
POST /settings/disconnect      — revoke Google access, xóa tokens
```

### 7.5. Upload

```
POST /upload                   — upload file (PDF/DOCX), trigger pipeline ngay
GET  /upload/:id/status        — kiểm tra trạng thái xử lý file upload
```

---

## 8. Frontend Pages

### 8.1. Page structure

```
/                     — redirect → /tasks hoặc /login
/login                — Google OAuth button
/tasks                — Task list (main page)
/tasks/:id            — Task detail + edit
/conflicts            — Conflict list + resolve UI
/sync                 — Sync status + history + manual trigger
/settings             — Sync config + notification config + disconnect
```

### 8.2. Task list UI requirements

- Filter by: status (pending/confirmed/dismissed), source (gmail/drive/upload), has deadline, has conflict
- Sort by: deadline (asc), created_at (desc)
- Inline actions: confirm, dismiss, edit deadline
- Badge: missing fields, conflict indicator
- Real-time sync status indicator (polling `/sync/status` mỗi 30s khi user online)

### 8.3. Conflict view

- Hiển thị 2 nguồn cạnh nhau
- Highlight field bị conflict
- Button: "Dùng nguồn A" / "Dùng nguồn B" / "Bỏ qua"

---

## 9. Security Design

### 9.1. OAuth token management

- Access token và refresh token được lưu **encrypted** trong DB (AES-256)
- Key encryption được lấy từ environment variable, không hardcode
- Token không bao giờ được expose ra response API hoặc frontend
- Refresh token tự động renew khi access token hết hạn (trong MCP calls)

### 9.2. Data isolation

- Mọi query đều phải có `WHERE user_id = :current_user_id`
- Không có endpoint nào trả về data của user khác
- File upload được lưu vào S3 với prefix `{user_id}/` và signed URLs

### 9.3. Session management

- Session token dạng JWT, expiry 7 ngày
- Revoke toàn bộ sessions khi user disconnect Google account
- Rate limit: 60 requests/phút per user trên các endpoints quan trọng

---

## 10. Local Development Setup

### 10.1. Services cần chạy

```
PostgreSQL 15      — port 5432
Redis              — port 6379
FastAPI backend-api — port 8000
Agent worker       — background service (systemd)
Next.js frontend   — port 3000
```

Không dùng Docker. Môi trường dev/staging/prod chạy trực tiếp trên AWS EC2 bằng systemd/PM2.

Python dependencies dùng **một môi trường ảo chung ở root project**:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Test command chuẩn từ root (không còn conflict import `app` giữa 2 module):

```bash
./scripts/test_all.sh
```

### 10.2. Environment variables cần thiết

```
# Google OAuth
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI

# LLM
GEMINI_API_KEY

# Database
DATABASE_URL           — postgresql://user:pass@localhost:5432/taskbot

# Redis
REDIS_URL              — redis://localhost:6379

# Security
JWT_SECRET
ENCRYPTION_KEY         — cho token storage

# App
SYNC_GMAIL_INTERVAL    — minutes, default 15
SYNC_DRIVE_INTERVAL    — minutes, default 30
```

### 10.3. Database migrations

Dùng Alembic (Python). Thứ tự tạo bảng:

1. `users`
2. `sync_states`
3. `source_documents`
4. `pipeline_runs`
5. `tasks`
6. `conflicts`

---

## 11. Deployment (AWS EC2)

### 11.1. Services trên EC2 (AWS-native, non-Docker)

```
System services:
  - postgresql-15
  - redis-server
  - taskbot-backend-api    (FastAPI, systemd, :8000)
  - taskbot-agent-worker   (APScheduler + LangGraph, systemd)
  - taskbot-frontend       (Next.js, PM2, :3000)

Nginx (reverse proxy):
  - / → frontend :3000
  - /api → backend-api :8000
```

### 11.2. S3

- Bucket: `taskbot-uploads-{env}`
- Prefix: `{user_id}/{upload_id}.{ext}`
- Lifecycle rule: xóa file sau 30 ngày nếu đã processed

### 11.3. Process restart

- systemd restart policy: `always` cho `taskbot-backend-api` và `taskbot-agent-worker`
- PM2 auto-start cho `taskbot-frontend`
- Scheduler tự resume jobs từ Redis khi restart
- Sync state trong DB đảm bảo không bị duplicate khi restart

---

## 12. Testing Strategy

### 12.1. Unit tests

- `test_normalization.py` — deadline normalization logic
- `test_conflict_detection.py` — conflict detection rules
- `test_dedup.py` — content hash + dedup logic
- `test_parser.py` — email/PDF/DOCX parsing

### 12.2. Integration tests

- `test_pipeline.py` — LangGraph pipeline end-to-end với mock LLM + mock MCP
- `test_sync.py` — scheduler job với mock Gmail/Drive responses
- `test_api.py` — API endpoints với test DB

### 12.3. Manual E2E checklist (trước mỗi release)

```
□ Connect Google account thành công
□ Trigger manual sync → Gmail messages được pull
□ Task được extract và hiển thị trên UI
□ Calendar event được tạo cho task có deadline
□ Conflict được detect và hiển thị đúng
□ Upload PDF/DOCX → task được extract
□ Disconnect account → tokens được revoke
```
