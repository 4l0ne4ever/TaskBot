# PHIẾU ĐỀ XUẤT ĐỒ ÁN TỐT NGHIỆP

**Trường:** Đại học Bách Khoa Hà Nội  
**Khoa:** Công nghệ Thông tin và Truyền thông  
**Chương trình:** Việt Nam – Nhật Bản (IT-E6)  
**Năm học:** 2025 – 2026

---

| Thông tin                    | Chi tiết                     |
| ---------------------------- | ---------------------------- |
| Họ và tên sinh viên          | Dương Công Thuyết            |
| Mã số sinh viên              | **********\_\_**********     |
| Lớp / Khóa                   | IT-E6 / K67                  |
| Email                        | sh1rohasbeencursed@gmail.com |
| Giảng viên hướng dẫn dự kiến | **********\_\_**********     |

---

## 1. Tên đề tài

**Xây dựng hệ thống AI tự động trích xuất, chuẩn hóa và theo dõi công việc từ email và tài liệu**

_(English: AI-powered Task Extraction, Normalization and Tracking System from Emails and Documents)_

---

## 2. Đặt vấn đề

Trong môi trường làm việc hiện đại, thông tin công việc liên tục xuất hiện dưới dạng không cấu trúc qua email, file đính kèm, và tài liệu được chia sẻ. Người dùng phải tự đọc, tự tổng hợp, và tự nhớ các deadline — dễ dẫn đến bỏ sót hoặc nhầm lẫn.

Bài toán cụ thể:

- **Phân tán:** Cùng một công việc có thể được đề cập trong email, file DOCX đính kèm, và tài liệu Google Drive — không có điểm tổng hợp duy nhất
- **Mơ hồ:** Deadline thường được viết dạng tương đối (_"cuối tuần"_, _"sớm nhất có thể"_) thay vì ngày cụ thể
- **Mâu thuẫn:** Cùng một task có thể xuất hiện với thông tin khác nhau ở các nguồn khác nhau
- **Thụ động:** Người dùng phải tự check email/Drive để biết có task mới — không có hệ thống nào chủ động thông báo

Các công cụ hiện tại (Gmail, Google Tasks, Notion) không giải quyết được chuỗi này end-to-end: từ đọc dữ liệu thô → trích xuất task → chuẩn hóa → phát hiện conflict → thông báo chủ động.

---

## 3. Mục tiêu sản phẩm

Xây dựng một **AI bot** có khả năng:

1. **Kết nối** với Gmail, Google Drive và nhận file upload trực tiếp
2. **Tự động trích xuất** thông tin công việc từ nội dung không cấu trúc
3. **Chuẩn hóa** deadline và thông tin mơ hồ thành dữ liệu có cấu trúc
4. **Phát hiện** trường thiếu và mâu thuẫn giữa các nguồn
5. **Thông báo chủ động** qua Google Calendar / reminder khi có task mới hoặc deadline gần
6. **Cung cấp UI** để xem, tìm kiếm và quản lý toàn bộ task đã tổng hợp
7. **Tự động cập nhật task** khi thông tin thay đổi ở email/nguồn sau (ví dụ: deadline bị lùi)

---

## 4. Phạm vi chức năng

### 4.1. Nguồn dữ liệu đầu vào

| Nguồn                              | Cơ chế                                           | Ghi chú                             |
| ---------------------------------- | ------------------------------------------------ | ----------------------------------- |
| **Gmail**                          | Gmail MCP server — đọc inbox, thread, attachment | Theo dõi label/folder được chỉ định |
| **File upload trực tiếp**          | UI upload — hỗ trợ PDF, DOCX, TXT                | Xử lý ngay sau khi upload           |
| **Google Drive — file của user**   | Drive MCP server — đọc file trong My Drive       | Theo folder được chỉ định           |
| **Google Drive — file được share** | Drive MCP server — đọc Shared with me            | Cần user cấp quyền một lần          |

### 4.2. Cơ chế retrieval và đồng bộ

| Nguồn        | Cơ chế đồng bộ                                      | Chu kỳ mặc định             |
| ------------ | --------------------------------------------------- | --------------------------- |
| Gmail        | Polling định kỳ — đọc email mới kể từ lần sync cuối | Mỗi 15 phút (cấu hình được) |
| Google Drive | Polling định kỳ — phát hiện file mới hoặc được sửa  | Mỗi 30 phút (cấu hình được) |
| File upload  | Xử lý ngay lập tức (on-demand)                      | Không áp dụng               |

> **Lưu ý:** Chu kỳ sync có thể cấu hình theo nhu cầu người dùng (từ 5 phút đến 24 giờ). Ngoài polling tự động, user có thể trigger sync thủ công bất cứ lúc nào từ UI.

### 4.3. AI Processing Pipeline

```
Input (email / file / Drive doc)
    ↓
[1] Ingestion & Preprocessing   — parse format, tách đoạn, nhận dạng ngữ cảnh
    ↓
[2] Extraction Agent            — trích xuất task title, deadline, assignee từ text thô
    ↓
[3] Normalization Agent         — chuẩn hóa deadline → ISO date, tên người → danh sách chuẩn
    ↓
[4] Validation Agent            — phát hiện missing fields + conflict detection
    ↓
[5] Notification Dispatcher     — gửi thông báo qua Google Calendar / reminder
    ↓
Structured Task Store (PostgreSQL)
```

### 4.4. Task Schema

```json
{
  "task_id": "string",
  "title": "string",
  "assignee": "string | null",
  "deadline": "ISO 8601 date | null",
  "priority": "high | medium | low | null",
  "source_type": "gmail | drive | upload",
  "source_ref": "message_id / file_id / upload_id",
  "extracted_at": "ISO 8601 datetime",
  "missing_fields": ["assignee", "deadline"],
  "conflicts": [
    {
      "type": "deadline_conflict | assignee_conflict",
      "description": "string",
      "sources": ["ref_a", "ref_b"]
    }
  ],
  "notification_sent": true,
  "calendar_event_id": "string | null"
}
```

### 4.5. Định nghĩa mâu thuẫn (giới hạn 2 loại)

| Loại                  | Định nghĩa                                                                  | Ví dụ                                                                                          |
| --------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Deadline conflict** | Hai nguồn đề cập cùng một task nhưng đưa ra hai mốc thời gian loại trừ nhau | Email thread: _"nộp báo cáo thứ Sáu"_ — file DOCX đính kèm: _"deadline thứ Ba"_                |
| **Assignee conflict** | Hai nguồn chỉ định người phụ trách loại trừ nhau cho cùng một task          | Email: _"chỉ Nguyễn phụ trách phần này"_ — Drive doc: _"Trần là người chịu trách nhiệm chính"_ |

> Nhiều người cùng làm một task **không** phải conflict. Conflict chỉ xảy ra khi hai nguồn **loại trừ nhau** về logic.

### 4.6. Thông báo và tích hợp

| Kênh                         | Nội dung                                          | Điều kiện trigger                             |
| ---------------------------- | ------------------------------------------------- | --------------------------------------------- |
| **Google Calendar**          | Tạo event với title = task title, ngày = deadline | Khi task có deadline cụ thể sau normalization |
| **In-app reminder**          | Notification trong UI                             | 24h và 1h trước deadline                      |
| **Email summary** (tùy chọn) | Tóm tắt task mới trong ngày                       | Mỗi sáng, cấu hình được                       |

### 4.7. Giới hạn phạm vi (version 1)

- Không tích hợp Slack, Zalo, Teams, Outlook (có thể mở rộng qua MCP adapter trong v2)
- Không xử lý real-time event stream quy mô lớn
- Không nhận dạng ảnh hoặc scan tài liệu (chỉ text-based PDF/DOCX)
- Assignee normalization trong phạm vi danh sách người dùng đã đăng ký trong hệ thống

---

## 5. Kiến trúc kỹ thuật

### 5.1. Stack công nghệ

| Thành phần         | Công nghệ                         | Ghi chú                               |
| ------------------ | --------------------------------- | ------------------------------------- |
| AI / Orchestration | LangGraph 1.x                     | Multi-agent pipeline, state graph     |
| LLM                | Groq (Llama 3.3 70B) API         | Extraction, normalization, validation |
| MCP — Gmail        | Gmail MCP Server                  | Đọc inbox, thread, attachment         |
| MCP — Drive        | `drive-mcp-server` (HTTP bridge trong repo) + Google Drive API | Đọc file My Drive + Shared (token user) |
| MCP — Calendar     | Google Calendar MCP Server        | Tạo event, reminder                   |
| Backend API        | Python 3.11+, FastAPI             | REST API + auth + settings            |
| Agent Module       | Python 3.11+, LangGraph Worker    | AI pipeline + scheduler execution      |
| Database           | PostgreSQL 15+                    | Task store, sync state, user config   |
| Cache / Queue      | Redis                             | Job queue cho scheduler, dedup        |
| File Parsing       | PyMuPDF (PDF), python-docx (DOCX) | Extract text từ file                  |
| Frontend           | Next.js 14, React, TailwindCSS    | UI dashboard                          |
| Auth               | Clerk + OAuth 2.0 (Google)        | Session auth + Google data access     |
| Cloud              | AWS EC2 (t3.small), S3            | Hosting, file storage                 |
| Runtime/Deploy     | Docker Compose + Nginx (tuỳ chọn) | **Dev & triển khai mặc định:** `docker-compose.yml` (Postgres, Redis, backend, agent, frontend). EC2 có thể `scripts/deploy_stack.sh`; vẫn giữ lựa chọn legacy systemd + PM2 (`deploy.sh`) |

**MCP:** Trong repo chỉ có **HTTP client** gọi MCP server bên ngoài (URL cấu hình `.env`); không bundle MCP server trong Docker. Gmail/Calendar có endpoint hosted; Drive cần server tự triển khai hoặc URL riêng.

### 5.2. Luồng đồng bộ tự động

```
APScheduler (mỗi 15/30 phút)
    ↓
Gọi Gmail MCP → lấy email mới kể từ last_sync_timestamp
Gọi Drive MCP → lấy file mới/sửa kể từ last_sync_timestamp
    ↓
Đưa vào AI Processing Pipeline
    ↓
Lưu task mới → PostgreSQL
    ↓
Notification Dispatcher → Google Calendar API
    ↓
Cập nhật last_sync_timestamp
```

---

## 6. Đánh giá hệ thống

### 6.1. Hai chiều đánh giá

Sản phẩm được đánh giá trên cả hai chiều: **chất lượng AI** và **vận hành thực tế**.

#### Chiều 1 — Chất lượng trích xuất (trên corpus có nhãn)

- **Dataset:** 200–300 mẫu email/tài liệu tổng hợp có gán nhãn thủ công
- **Gán nhãn:** Một người gán chính theo rubric cố định; spot-check 15–20% bởi người thứ hai
- **Rubric deadline:** Biểu thức tương đối (_"thứ Sáu tới"_) → ngày tuyệt đối tính theo ngày email gửi; không có mốc thời gian → `null`

**Metrics:**

| Metric                | Mô tả                                                  |
| --------------------- | ------------------------------------------------------ |
| F1 per field          | Precision/Recall/F1 cho task title, assignee, deadline |
| Deadline exact match  | Ngày ISO khớp hoàn toàn                                |
| Deadline near match   | ±1 ngày (cho biểu thức mơ hồ)                          |
| Conflict detection F1 | Precision/Recall/F1 trên tập conflict có nhãn          |

**So sánh phương pháp:**

| Phương pháp                        | Mô tả                                            |
| ---------------------------------- | ------------------------------------------------ |
| Baseline 1 — Rule-based            | Regex + heuristic                                |
| Baseline 2 — Single LLM            | Một lần gọi LLM với full prompt                  |
| **Đề xuất — Multi-stage pipeline** | 3 agent: Extraction → Normalization → Validation |

#### Chiều 2 — Vận hành thực tế (trên Gmail/Drive thật)

- Kết nối Gmail và Drive thực của tester (dữ liệu không nhạy cảm)
- Đánh giá end-to-end: từ sync → extract → calendar event
- Đo: độ trễ sync (thực tế vs chu kỳ cấu hình), tỷ lệ task bị bỏ sót khi sync, độ chính xác calendar event được tạo

### 6.2. Mục tiêu chất lượng

| Metric                                      | Mục tiêu                   | Xử lý nếu không đạt                     |
| ------------------------------------------- | -------------------------- | --------------------------------------- |
| F1 extraction (title + deadline + assignee) | ≥ 0.75                     | Phân tích lỗi chi tiết theo loại        |
| Conflict detection Precision                | ≥ 0.70                     | Phân tích false positive pattern        |
| Pipeline vs Single LLM                      | Cải thiện ít nhất 1 metric | Lý giải nguyên nhân nếu không cải thiện |

---

## 7. Bảo mật (cơ bản — v1)

- OAuth 2.0 cho Gmail và Google Drive (không lưu password)
- Token được lưu encrypted, không expose ra frontend
- User chỉ thấy task của chính mình (row-level isolation trong DB)
- Option xóa toàn bộ dữ liệu của một user (right to delete)
- **Phạm vi mở rộng (nếu có thời gian):** Rate limiting, audit log truy cập, role-based access control cho team use case

---

## 8. Kế hoạch thực hiện

| Giai đoạn | Nội dung                                                       | Thời gian  |
| --------- | -------------------------------------------------------------- | ---------- |
| 1         | Nghiên cứu, thiết kế schema, xây rubric, tạo dataset có nhãn   | Tuần 1–3   |
| 2         | Gmail MCP + Drive MCP integration, ingestion pipeline, MVP API | Tuần 4–5   |
| 3         | Extraction Agent + Normalization Agent                         | Tuần 6–7   |
| 4         | Validation Agent (conflict + missing field detection)          | Tuần 8     |
| 5         | APScheduler polling, Google Calendar notification              | Tuần 9     |
| 6         | Baseline 1 + Baseline 2, chạy evaluation trên corpus có nhãn   | Tuần 10–11 |
| 7         | UI (task list, search, conflict view, sync status, settings)   | Tuần 12    |
| 8         | End-to-end test trên Gmail/Drive thật, bug fixes               | Tuần 13    |
| 9         | Hoàn thiện báo cáo, chuẩn bị bảo vệ                            | Tuần 14–16 |

---

## 9. Đóng góp của đề tài

1. **Sản phẩm hoạt động thực tế:** AI bot kết nối Gmail/Drive thật, tự động trích xuất và chuẩn hóa task, thông báo qua Google Calendar — không dừng ở demo

2. **Pipeline đa bước có kiểm chứng:** So sánh định lượng giữa rule-based / single LLM / multi-stage pipeline trên cùng corpus có nhãn

3. **Định nghĩa và đánh giá conflict detection:** 2 loại mâu thuẫn được định nghĩa rõ, đo được, có kết quả thực nghiệm

4. **Kiến trúc MCP-based ingestion:** Tích hợp đa nguồn (Gmail, Drive, upload) qua MCP protocol — có thể mở rộng sang nền tảng khác bằng cách thêm MCP adapter

---

## 10. Giới hạn và hướng phát triển

**Giới hạn được thừa nhận (v1):**

- Dataset 200–300 mẫu là pilot, không claim generalizability rộng
- Conflict detection giới hạn 2 loại — conflict phức tạp hơn nằm ngoài phạm vi
- Không hỗ trợ ảnh scan, voice note, hay nền tảng ngoài Google
- Polling không phải real-time push notification

**Hướng v2 nếu có thời gian:**

- Mở rộng sang Slack/Teams qua MCP adapter
- Push notification qua webhook thay vì polling
- Role-based access control cho team
- Active learning từ feedback người dùng (confirm/reject task được trích xuất)

---

_Hà Nội, tháng \_\_\_ năm 2026_

|                         |                          |
| ----------------------- | ------------------------ |
| **Sinh viên đề xuất**   | **Giảng viên hướng dẫn** |
| _(Ký và ghi rõ họ tên)_ | _(Ý kiến và chữ ký)_     |
|                         |                          |
| **Dương Công Thuyết**   |                          |
