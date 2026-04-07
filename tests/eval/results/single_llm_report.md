# Evaluation Report: single

Generated: 2026-04-03T20:02:57
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.8409 | 0.9522 | 0.8931 |
| Assignee | 0.9150 | 0.8626 | 0.8880 |
| Conflict | 0.9600 | 0.9600 | 0.9600 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.4793 |
| Deadline Near (+-1d) | 0.6322 |

## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.5517 | 0.2222 | 0.0000 | 0.2000 | 0.9474 |
| conflict_deadline | 15 | 0.6222 | 0.9655 | 0.1333 | 0.5333 | 1.0000 |
| doc_meeting_notes | 15 | 0.9688 | 0.9841 | 0.0000 | 0.3438 | 0.0000 |
| doc_simple | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_forwarded | 8 | 1.0000 | 1.0000 | 0.0000 | 0.1250 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 0.8000 | 0.4000 | 0.4000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 0.4286 | 0.0000 | 0.4286 | 0.0000 |
| edge_noisy_long | 10 | 0.6667 | 1.0000 | 0.9000 | 0.9000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 0.9000 | 0.3000 | 0.6000 | 0.0000 |
| edge_special_format | 10 | 0.8889 | 1.0000 | 0.2000 | 0.5000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.8421 | 0.7647 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 0.9831 | 0.8136 | 0.4667 | 0.4667 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0000 |
| missing_deadline | 10 | 0.7500 | 0.5000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.7679**
- Edge case categories weighted Title F1: **0.7222**
- Delta: **-0.0456**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 73 | 29.2% |
| hallucinated_task | 46 | 18.4% |
| missed_assignee | 36 | 14.4% |
| deadline_off_by_one | 28 | 11.2% |
| wrong_assignee | 21 | 8.4% |
| missed_task | 13 | 5.2% |
| complete_miss | 7 | 2.8% |
| false_positive_extraction | 4 | 1.6% |
| missed_conflict | 1 | 0.4% |
| false_conflict | 1 | 0.4% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | false_conflict | false_positive_extraction | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_assignee | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 2 | 0 | 0 | 9 | 8 | 1 | 2 | 6 | 8 |
| conflict_deadline | 0 | 6 | 0 | 0 | 15 | 1 | 0 | 1 | 0 | 7 |
| doc_meeting_notes | 0 | 5 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 10 |
| edge_forwarded | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| edge_mixed_lang | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 6 |
| edge_nickname | 0 | 3 | 0 | 0 | 0 | 4 | 0 | 0 | 4 | 4 |
| edge_noisy_long | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 1 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 4 |
| edge_special_format | 0 | 3 | 1 | 0 | 5 | 0 | 0 | 0 | 0 | 5 |
| edge_tricky_negative | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| email_ambiguous | 2 | 0 | 0 | 0 | 2 | 7 | 0 | 4 | 1 | 0 |
| email_no_task | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| email_simple | 1 | 0 | 0 | 0 | 0 | 6 | 0 | 1 | 5 | 16 |
| missing_assignee | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| missing_deadline | 4 | 0 | 0 | 0 | 0 | 6 | 0 | 4 | 2 | 0 |

## 6. Sample-Level Details (Errors Only)

### mx-189 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Đỗ | 2026-04-10 | pri=None
  - P: "update NDA contract" | ễốộ Đô | 2026-04-08 | pri=high

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-001 (email_simple, vi)

**Input:** Chào team,

Nhờ Hoàng Nam chuẩn bị bảng số liệu tài chính trong 3 ngày tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | 2026-04-02 | pri=None
  - P: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | 2026-03-31 | pri=medium

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None
  - P: "hoàn thành bản đánh giá nhân sự trước thứ Sáu tới" | Nguyễn | 2026-04-08 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-124 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-02

Tham dự: Đặng Tuấn Kiệt, Dương Thị Mai

Action items:
- Đặng Tuấn Kiệt: báo cáo tháng 3 trước thứ Sáu
- Dương Thị Mai: proposal hợp tác trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Báo cáo tháng 3" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None
  - E: "Proposal hợp tác" | Dương Thị Mai | 2026-04-03 | pri=None
  - P: "báo cáo tháng 3" | Đặng Tuấn Kiệt | 2026-04-02 | pri=null
  - P: "proposal hợp tác" | Dương Thị Mai | 2026-04-02 | pri=null

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 2, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-123 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-01

Tham dự: Phạm Hương, Lê Minh Đức

Action items:
- Phạm Hương: biên bản họp trước thứ Sáu
- Lê Minh Đức: tài liệu thiết kế trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Biên bản họp" | Phạm Hương | 2026-04-03 | pri=None
  - E: "Tài liệu thiết kế" | Lê Minh Đức | 2026-04-03 | pri=None
  - P: "biên bản họp trước thứ Sáu" | Phạm Hương | 2026-04-01 | pri=null
  - P: "tài liệu thiết kế trước thứ Sáu" | Lê Minh Đức | 2026-04-01 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-002 (email_simple, en)

**Input:** Hi team,

Please ask Charlie to compile the test results by this Friday. Thanks.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Compile test results" | Charlie | 2026-04-03 | pri=None
  - P: "compile the test results" | Charlie | 2026-03-25 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-247 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Hương ơi, viết báo cáo Q1 trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết báo cáo Q1" | Hương | 2026-04-03 | pri=None
  - P: "viết báo cáo Q1 trước thứ Sáu" | Bạn Hương | 2026-04-02 | pri=null

**Errors:** missed_assignee, wrong_assignee, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-128 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-06

Tham dự: Huỳnh Minh Tâm, Lê Minh Đức

Action items:
- Huỳnh Minh Tâm: tài liệu thiết kế trước thứ Sáu
- Lê Minh Đức: báo cáo Q1 trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Huỳnh Minh Tâm | 2026-04-10 | pri=None
  - E: "Báo cáo Q1" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "tài liệu thiết kế trước thứ Sáu" | Huỳnh Minh Tâm | 2026-04-08 | pri=null
  - P: "báo cáo Q1 trước thứ Sáu" | Lê Minh Đức | 2026-04-08 | pri=null

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 1}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-157 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "wireframe trang chủ" | Đỗ Văn Hải | 2026-04-02 | pri=null
  - P: "wireframe trang chủ" | Lê Minh Đức | null | pri=null

**Errors:** hallucinated_task, missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### sf-240 (edge_special_format, en)
Edge tags: special_format, checklist with done item

**Input:** Sprint 14 checklist:

☐ financial spreadsheet — Charlie — by Friday
☐ test results — Quinn — by Friday
☑ Complete UI design (done)

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Financial spreadsheet" | Charlie | 2026-04-10 | pri=None
  - E: "Test results" | Quinn | 2026-04-10 | pri=None
  - P: "financial spreadsheet" | Charlie | 2026-04-09 | pri=None
  - P: "test results" | Quinn | 2026-04-09 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 2, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-235 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ báo cáo tháng 3 — Lý Hoàng Long — trước thứ Sáu
☐ bảng số liệu tài chính — Hoàng Nam — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Báo cáo tháng 3" | Lý Hoàng Long | 2026-04-03 | pri=None
  - E: "Bảng số liệu tài chính" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "báo cáo tháng 3" | Lý Hoàng Long | 2026-03-26 | pri=None
  - P: "bảng số liệu tài chính" | Hoàng Nam | 2026-03-26 | pri=None
  - P: "Hoàn thành thiết kế UI" | None | None | pri=None

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-205 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-02
Subject: Phân công

Nhờ Đỗ kiểm tra hợp đồng NDA trước thứ Sáu.

---------- End forwarded ----------

FYI team, mọi ...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Kiểm tra hợp đồng NDA" | Đỗ | 2026-04-03 | pri=None
  - P: "Kiểm tra hợp đồng NDA trước thứ Sáu" | Đỗ | 2026-04-02 | pri=null

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-246 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Mai ơi, soạn hợp đồng NDA trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Soạn hợp đồng NDA" | Mai | 2026-04-03 | pri=None
  - P: "soạn hợp đồng NDA trước thứ Sáu" | Bạn Mai | 2026-04-01 | pri=null

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-241 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ bản kế hoạch dự án — Lê Minh Đức — trước thứ Sáu
☐ bản đánh giá nhân sự — Vũ Thảo — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Bản kế hoạch dự án" | Lê Minh Đức | 2026-04-10 | pri=None
  - E: "Bản đánh giá nhân sự" | Vũ Thảo | 2026-04-10 | pri=None
  - P: "bản kế hoạch dự án" | Lê Minh Đức | 2026-04-01 | pri=None
  - P: "bản đánh giá nhân sự" | Vũ Thảo | 2026-04-01 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-029 (email_simple, vi)

**Input:** Hi Phan Đức Anh,

Bạn hoàn thành bản kế hoạch dự án trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Hoàn thành bản kế hoạch dự án" | Phan Đức Anh | 2026-04-01 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-180 (missing_assignee, vi)

**Input:** Ai đó hoàn thành báo cáo Q1 trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo Q1" | None | 2026-04-10 | pri=None
  - P: "hoàn thành báo cáo Q1" | None | 2026-04-08 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-203 (edge_forwarded, en)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-03-31
Subject: Assignment

Please ask Eve to check the partnership proposal by Friday.

---------- End forwarded ---------...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Check partnership proposal" | Eve | 2026-04-03 | pri=None
  - P: "Check partnership proposal" | Eve | 2026-04-01 | pri=low

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-025 (email_simple, vi)

**Input:** @Nguyễn — chuẩn bị tài liệu thiết kế trước thứ Sáu này. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị tài liệu thiết kế" | Nguyễn | 2026-04-10 | pri=None
  - P: "chôn đượng tài liệu thiết kế trước thứ Sáu này" | Đượng | 2026-04-08 | pri=high

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "nộp tài liệu thiết kế trước thứ Sáu" | Ngô Thanh Tùng | 2026-04-01 | pri=null
  - P: "nộp tài liệu thiết kế trước ngày mai" | Ngô Thanh Tùng | 2026-04-02 | pri=null

**Errors:** hallucinated_task, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-141 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-02]
Bob, please submit the partnership proposal by Friday.

[Email 2 — 2026-04-04]
Update: the partnership proposal is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Partnership proposal" | Bob | 2026-04-05 | pri=None
  - P: "submit the partnership proposal" | Bob | 2026-04-08 | pri=medium
  - P: "submit the partnership proposal" | Bob | 2026-04-05 | pri=medium

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nn-245 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Thảo ơi, chỉnh sửa tài liệu thiết kế trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Thảo | 2026-04-03 | pri=None
  - P: "chỉnh sửa tài liệu thiết kế trước thứ Sáu" | Bạn Thảo | 2026-04-01 | pri=null

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-153 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lê Minh Đức phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đặng Tuấn Kiệt phụ trách bản đánh giá nhân sự thay Lê Minh Đức.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None
  - P: "nộp bản đánh giá nhân sự trước thứ Sáu" | Đặng Tuấn Kiệt | 2026-04-02 | pri=null

**Errors:** deadline_off_by_one, missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "complete the API documentation" | Frankie | 2026-04-09 | pri=medium

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "update Q1 report" | Hoàng | 2026-04-07 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-248 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Di, submit the Q1 report by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit Q1 report" | Di | 2026-04-03 | pri=None
  - P: "submit the Q1 report" | Di | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-243 (edge_special_format, en)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Bob] project plan (due: Friday)
* [Charlie] partnership proposal (due: Friday)
* [DONE] Deploy API endpoint

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Project plan" | Bob | 2026-04-10 | pri=None
  - E: "Partnership proposal" | Charlie | 2026-04-10 | pri=None
  - P: "project plan" | Bob | 2026-04-08 | pri=None
  - P: "partnership proposal" | Charlie | 2026-04-08 | pri=None
  - P: "Deploy API endpoint" | None | None | pri=None

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-094 (email_ambiguous, en)

**Input:** Could Steve work on the API documentation sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Submit API documentation" | Steve | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-143 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-04]
Nguyễn, hợp đồng NDA nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-06]
Cập nhật: hợp đồng NDA cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Hợp đồng NDA" | Nguyễn | 2026-04-07 | pri=None
  - P: "nộp hợp đồng NDA trước thứ Sáu" | Nguyễn | 2026-04-08 | pri=null
  - P: "nộp hợp đồng NDA trước ngày mai" | Nguyễn | 2026-04-07 | pri=null

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 2, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None
  - P: "Báo cáo tháng 3" | Phan Đức Anh | 2026-04-02 | pri=null
  - P: "Báo cáo tháng 3" | Phạm Hương | null | pri=null

**Errors:** hallucinated_task, missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-022 (email_simple, vi)

**Input:** Anh/chị Bùi Lan Anh ơi, nhờ hoàn thành bản kế hoạch dự án trước ngày 10 tháng 4 ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản kế hoạch dự án" | Bùi Lan Anh | 2026-04-10 | pri=None
  - P: "hoàn thành bản kế hoạch dự án" | Anh/chị Bùi Lan Anh | 2026-04-10 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-126 (doc_meeting_notes, en)

**Input:** Meeting Notes — 2026-04-04

Attendees: Henry, Ivy

Action items:
- Henry: API documentation by Friday
- Ivy: homepage wireframe by Friday

**Expected tasks:** 2 | **Predicted:** 2
  - E: "API documentation" | Henry | 2026-04-10 | pri=None
  - E: "Homepage wireframe" | Ivy | 2026-04-10 | pri=None
  - P: "API documentation" | Henry | 2026-04-08 | pri=null
  - P: "homepage wireframe" | Ivy | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-216 (edge_priority, en)
Edge tags: explicit_priority

**Input:** [URGENT] Paul, please update the API documentation by tomorrow. This is critical!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update API documentation" | Paul | 2026-04-08 | pri=high
  - P: "update the API documentation" | Paul | 2026-04-07 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-139 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-31]
Karen, please submit the test results by Friday.

[Email 2 — 2026-04-02]
Update: the test results is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Test results" | Karen | 2026-04-03 | pri=None
  - P: "submit the test results" | Karen | 2026-04-02 | pri=medium
  - P: "submit the test results" | null | 2026-04-03 | pri=medium

**Errors:** hallucinated_task, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-179 (missing_assignee, vi)

**Input:** Ai đó hoàn thành hợp đồng NDA trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành hợp đồng NDA" | None | 2026-04-10 | pri=None
  - P: "hoàn thành hợp đồng NDA trước thứ Sáu" | None | 2026-04-08 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-133 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-11

Tham dự: Trần Thị Bình, Phạm Hương

Action items:
- Trần Thị Bình: hợp đồng NDA trước thứ Sáu
- Phạm Hương: báo cáo tháng 3 trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Hợp đồng NDA" | Trần Thị Bình | 2026-04-17 | pri=None
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-17 | pri=None
  - P: "hợp đồng NDA trước thứ Sáu" | Trần Thị Bình | 2026-04-08 | pri=null
  - P: "báo cáo tháng 3 trước thứ Sáu" | Phạm Hương | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-176 (missing_assignee, vi)

**Input:** Task: báo cáo tháng 3 — deadline thứ Sáu. Chưa assign.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo tháng 3" | None | 2026-04-10 | pri=None
  - P: "báo cáo tháng 3" | None | 2026-04-02 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nl-195 (edge_noisy_long, vi)
Edge tags: noisy, long_text, signature

**Input:** Chào team,

Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:

- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái
- Chi phí marketing đã được tối ưu
- Nhóm R&D đang nghi...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Soạn bản đánh giá nhân sự" | Huỳnh | 2026-04-10 | pri=None
  - P: "Soạn bản đánh giá nhân sự" | Huỳnh | 2026-04-10 | pri=null
  - P: "Báo cáo chính sách WFH" | null | null | pri=null

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-017 (email_simple, en)

**Input:** Hey Karen,

Could you send the project plan by next Friday? Appreciate it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send project plan" | Karen | 2026-04-10 | pri=None
  - P: "Send project plan" | Karen | 2026-04-08 | pri=low

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-178 (missing_assignee, vi)

**Input:** Ai đó hoàn thành bảng số liệu tài chính trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bảng số liệu tài chính" | None | 2026-04-10 | pri=None
  - P: "hoàn thành bảng số liệu tài chính trước thứ Sáu" | None | 2026-04-02 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-175 (missing_assignee, vi)

**Input:** Cần hoàn thành kết quả kiểm thử trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành kết quả kiểm thử" | None | 2026-04-03 | pri=None
  - P: "hoan thanh ket qua kiem thu" | None | 2026-04-02 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-211 (edge_priority, en)
Edge tags: explicit_priority

**Input:** High priority: Steve, prepare the design document within 2 days.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Prepare design document" | Steve | 2026-04-04 | pri=high
  - P: "prepare the design document" | Steve | 2026-04-03 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-140 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-01]
Phan Đức Anh, wireframe trang chủ nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-03]
Cập nhật: wireframe trang chủ cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Phan Đức Anh | 2026-04-04 | pri=None
  - P: "wireframe trang chủ" | Phan Đức Anh | 2026-04-01 | pri=null
  - P: "wireframe trang chủ" | Phan Đức Anh | 2026-04-04 | pri=null

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-154 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Dương Thị Mai phụ trách kết quả kiểm thử, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Hoàng Nam phụ trách kết quả kiểm thử thay Dương Thị Mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Kết quả kiểm thử" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "nộp trước thứ Sáu" | Dương Thị Mai | 2026-04-02 | pri=null
  - P: "nộp trước thứ Sáu" | Hoàng Nam | 2026-04-02 | pri=null

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 2, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-125 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-03

Tham dự: Hoàng Nam, Dương Thị Mai

Action items:
- Hoàng Nam: bản kế hoạch dự án trước thứ Sáu
- Dương Thị Mai: bản đánh giá nhân sự trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Bản kế hoạch dự án" | Hoàng Nam | 2026-04-03 | pri=None
  - E: "Bản đánh giá nhân sự" | Dương Thị Mai | 2026-04-03 | pri=None
  - P: "bản kế hoạch dự án trước thứ Sáu" | Hoàng Nam | 2026-04-08 | pri=null
  - P: "bản đánh giá nhân sự trước thứ Sáu" | Dương Thị Mai | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nl-200 (edge_noisy_long, vi)
Edge tags: noisy, long_text, signature

**Input:** Chào team,

Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:

- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái
- Chi phí marketing đã được tối ưu
- Nhóm R&D đang nghi...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Cập nhật bản đánh giá nhân sự" | Huỳnh Minh Tâm | 2026-04-13 | pri=None
  - P: "Cập nhật bản đánh giá nhân sự" | Huỳnh Minh Tâm | 2026-04-13 | pri=null
  - P: "Báo cáo chính sách WFH" | null | null | pri=null

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-142 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-03]
Trần Thị Bình, tài liệu API docs nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-05]
Cập nhật: tài liệu API docs cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu API docs" | Trần Thị Bình | 2026-04-06 | pri=None
  - P: "nộp tài liệu API docs" | Trần Thị Bình | 2026-04-08 | pri=null
  - P: "nộp tài liệu API docs" | Trần Thị Bình | 2026-04-06 | pri=null

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-009 (email_simple, vi)

**Input:** Chào team,

Nhờ Vũ Thảo review bảng số liệu tài chính trước tuần tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review bảng số liệu tài chính" | Vũ Thảo | 2026-04-13 | pri=None
  - P: "review bảng số liệu tài chính" | Vũ Thảo | 2026-04-07 | pri=low

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-007 (email_simple, en)

**Input:** Hi team,

Please ask Tina to review the March report by end of month. Thanks.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Tina | 2026-04-30 | pri=None
  - P: "Review March report" | Tina | 2026-03-31 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nl-197 (edge_noisy_long, vi)
Edge tags: noisy, long_text, signature

**Input:** Chào team,

Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:

- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái
- Chi phí marketing đã được tối ưu
- Nhóm R&D đang nghi...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Review hợp đồng NDA" | Đặng | 2026-04-12 | pri=None
  - P: "Review hợp đồng NDA" | Đặng | 2026-04-12 | pri=null
  - P: "Báo cáo WFH" | null | null | pri=null

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-188 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Hi Phạm Hương, nhờ bạn review cái March report trước tuần tới. Cảm ơn nha.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Phạm Hương | 2026-04-13 | pri=None
  - P: "review March report" | Phạm Hương | 2026-04-10 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}


_...and 83 more error samples (see JSON for full details)._


## 7. Summary Statistics

- Fully correct samples: **117/250** (46.8%)
- Samples with errors: **133/250** (53.2%)