# Evaluation Report: single

Generated: 2026-04-03T21:28:49
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.8274 | 0.9338 | 0.8774 |
| Assignee | 0.9380 | 0.8664 | 0.9008 |
| Conflict | 0.8929 | 1.0000 | 0.9434 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.5620 |
| Deadline Near (+-1d) | 0.7190 |

## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.5926 | 0.4444 | 0.2000 | 0.4000 | 1.0000 |
| conflict_deadline | 15 | 0.6667 | 0.9655 | 0.2667 | 0.5333 | 0.9677 |
| doc_meeting_notes | 15 | 0.9688 | 0.9841 | 0.1562 | 0.5625 | 0.0000 |
| doc_simple | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_forwarded | 8 | 0.8750 | 0.9333 | 0.1250 | 0.1250 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 0.9000 | 0.4000 | 0.5000 | 0.0000 |
| edge_nickname | 7 | 0.8571 | 0.4615 | 0.2857 | 0.5714 | 0.0000 |
| edge_noisy_long | 10 | 0.6897 | 1.0000 | 0.9000 | 0.9000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 0.9000 | 0.3000 | 0.6000 | 0.0000 |
| edge_special_format | 10 | 0.9091 | 1.0000 | 0.5000 | 0.8000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.8205 | 0.7647 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 0.8667 | 0.8214 | 0.4667 | 0.5000 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 0.2000 | 0.8000 | 0.0000 |
| missing_deadline | 10 | 0.7500 | 0.5000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.7521**
- Edge case categories weighted Title F1: **0.6998**
- Delta: **-0.0522**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 58 | 23.2% |
| hallucinated_task | 50 | 20.0% |
| missed_assignee | 35 | 14.0% |
| deadline_off_by_one | 28 | 11.2% |
| missed_task | 18 | 7.2% |
| wrong_assignee | 15 | 6.0% |
| false_positive_extraction | 8 | 3.2% |
| complete_miss | 5 | 2.0% |
| false_conflict | 3 | 1.2% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | false_conflict | false_positive_extraction | hallucinated_task | missed_assignee | missed_task | wrong_assignee | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 2 | 0 | 0 | 7 | 6 | 2 | 4 | 6 |
| conflict_deadline | 0 | 4 | 1 | 0 | 12 | 1 | 1 | 0 | 7 |
| doc_meeting_notes | 0 | 6 | 0 | 0 | 1 | 1 | 1 | 0 | 6 |
| edge_forwarded | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 7 |
| edge_mixed_lang | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 5 |
| edge_nickname | 0 | 2 | 0 | 0 | 1 | 4 | 1 | 3 | 3 |
| edge_noisy_long | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 1 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 1 | 4 |
| edge_special_format | 0 | 3 | 2 | 0 | 4 | 0 | 0 | 0 | 2 |
| edge_tricky_negative | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0 |
| email_ambiguous | 1 | 0 | 0 | 0 | 3 | 7 | 4 | 1 | 0 |
| email_no_task | 0 | 0 | 0 | 5 | 5 | 0 | 0 | 0 | 0 |
| email_simple | 0 | 1 | 0 | 0 | 4 | 7 | 4 | 3 | 15 |
| missing_assignee | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| missing_deadline | 4 | 0 | 0 | 0 | 0 | 6 | 4 | 2 | 0 |

## 6. Sample-Level Details (Errors Only)

### mx-189 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Đỗ | 2026-04-10 | pri=None
  - P: "Update NDA" | Đỗ | 2026-04-11 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-001 (email_simple, vi)

**Input:** Chào team,

Nhờ Hoàng Nam chuẩn bị bảng số liệu tài chính trong 3 ngày tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | 2026-04-02 | pri=None
  - P: "Prepare financial report" | Hoang Nam | 2026-04-02 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None
  - P: "hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-04 | pri=high

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
  - P: "báo cáo tháng 3" | Đặng Tuấn Kiệt | 2026-04-04 | pri=None
  - P: "proposal hợp tác" | Dương Thị Mai | 2026-04-04 | pri=None

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
  - P: "biên bản họp" | Phạm Hương | 2026-04-04 | pri=None
  - P: "tài liệu thiết kế" | Lê Minh Đức | 2026-04-04 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 2, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-056 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Test feature/auth" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-247 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Hương ơi, viết báo cáo Q1 trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết báo cáo Q1" | Hương | 2026-04-03 | pri=None
  - P: "Viết báo cáo Q1" | Bạn Hương | 2026-04-04 | pri=None

**Errors:** missed_assignee, wrong_assignee, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-026 (email_simple, vi)

**Input:** Hi Phạm,

Bạn chỉnh sửa slide thuyết trình trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa slide thuyết trình" | Phạm | 2026-04-12 | pri=None
  - P: "edit slides" | Phạm | 2026-04-12 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-062 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Test feature/auth" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-008 (email_simple, vi)

**Input:** Gửi Trần Thị Bình,

Phiền bạn chuẩn bị wireframe trang chủ trước ngày mai.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị wireframe trang chủ" | Trần Thị Bình | 2026-04-07 | pri=None
  - P: "Prepare wireframe" | Trần Thị Bình | 2026-04-07 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Check NDA contract" | Đỗ | 2026-04-05 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-029 (email_simple, vi)

**Input:** Hi Phan Đức Anh,

Bạn hoàn thành bản kế hoạch dự án trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản kế hoạch dự án" | Phan Đức Anh | 2026-04-01 | pri=None
  - P: "Complete project plan" | Phan Đức Anh | 2026-04-01 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-180 (missing_assignee, vi)

**Input:** Ai đó hoàn thành báo cáo Q1 trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo Q1" | None | 2026-04-10 | pri=None
  - P: "Hoàn thành báo cáo Q1" | None | 2026-04-11 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "Nộp tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-04 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nn-245 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Thảo ơi, chỉnh sửa tài liệu thiết kế trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Thảo | 2026-04-03 | pri=None
  - P: "chỉnh sửa tài liệu" | Bạn Thảo | 2026-04-03 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-153 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lê Minh Đức phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đặng Tuấn Kiệt phụ trách bản đánh giá nhân sự thay Lê Minh Đức.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None
  - P: "bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-04 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "API doc" | Frankie | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "Update Q1 report" | Hoàng | 2026-04-10 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-248 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Di, submit the Q1 report by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit Q1 report" | Di | 2026-04-03 | pri=None
  - P: "Q1 report" | Di | 2026-04-05 | pri=None

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
  - P: "project plan" | Bob | 2026-04-11 | pri=None
  - P: "partnership proposal" | Charlie | 2026-04-11 | pri=None
  - P: "Deploy API endpoint" | None | None | pri=None

**Errors:** hallucinated_task, deadline_off_by_one, false_conflict
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 2, 'total': 2}, conflict={'tp': 0, 'fp': 1, 'fn': 0}

### dc-143 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-04]
Nguyễn, hợp đồng NDA nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-06]
Cập nhật: hợp đồng NDA cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Hợp đồng NDA" | Nguyễn | 2026-04-07 | pri=None
  - P: "NDA submission" | Nguyễn | 2026-04-11 | pri=None
  - P: "NDA submission" | None | 2026-04-07 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, false_conflict
**Scores:** title={'tp': 0, 'fp': 2, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 1, 'fn': 0}

### eval-126 (doc_meeting_notes, en)

**Input:** Meeting Notes — 2026-04-04

Attendees: Henry, Ivy

Action items:
- Henry: API documentation by Friday
- Ivy: homepage wireframe by Friday

**Expected tasks:** 2 | **Predicted:** 2
  - E: "API documentation" | Henry | 2026-04-10 | pri=None
  - E: "Homepage wireframe" | Ivy | 2026-04-10 | pri=None
  - P: "API doc" | Henry | 2026-04-10 | pri=None
  - P: "homepage wireframe" | Ivy | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 1}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-216 (edge_priority, en)
Edge tags: explicit_priority

**Input:** [URGENT] Paul, please update the API documentation by tomorrow. This is critical!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update API documentation" | Paul | 2026-04-08 | pri=high
  - P: "Update API docs" | Paul | 2026-04-07 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-229 (edge_tricky_negative, en)
Edge tags: tricky_negative, question

**Input:** Does anyone know when the API documentation is due?

**Expected tasks:** 0 | **Predicted:** 1
  - P: "API doc" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-176 (missing_assignee, vi)

**Input:** Task: báo cáo tháng 3 — deadline thứ Sáu. Chưa assign.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo tháng 3" | None | 2026-04-10 | pri=None
  - P: "báo cáo tháng 3" | None | 2026-04-04 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-082 (email_ambiguous, vi)

**Input:** Khi nào rảnh thì Ngô Thanh Tùng check lại hợp đồng NDA giúp.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Kiểm tra hợp đồng NDA" | Ngô Thanh Tùng | None | pri=None
  - P: "Check NDA" | Ngô Thanh Tùng | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-017 (email_simple, en)

**Input:** Hey Karen,

Could you send the project plan by next Friday? Appreciate it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send project plan" | Karen | 2026-04-10 | pri=None
  - P: "Send project plan" | Karen | 2026-04-11 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-175 (missing_assignee, vi)

**Input:** Cần hoàn thành kết quả kiểm thử trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành kết quả kiểm thử" | None | 2026-04-03 | pri=None
  - P: "Hoàn thành kết quả kiểm thử" | None | 2026-04-04 | pri=None

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

### mx-187 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update project plan asap, deadline là trước cuối tháng.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update project plan" | Đỗ | 2026-04-30 | pri=None
  - P: "update project plan" | ễốộ Đô | 2026-04-30 | pri=high

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-201 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-03-29
Subject: Phân công

Nhờ Nguyễn Văn An nộp bản kế hoạch dự án trước thứ Sáu.

---------- End forwarded ----------

FY...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Nộp bản kế hoạch dự án" | Nguyễn Văn An | 2026-04-03 | pri=None
  - P: "nộp bản kế hoạch dự án trước thứ Sáu" | Nguyễn Văn An | 2026-04-01 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-158 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lý Hoàng Long phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đỗ Văn Hải phụ trách wireframe trang chủ thay Lý Hoàng Long.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Đỗ Văn Hải | 2026-04-10 | pri=None
  - P: "wireframe trang chủ" | Lý Hoàng Long | 2026-04-02 | pri=null
  - P: "wireframe trang chủ" | Đỗ Văn Hải | null | pri=null

**Errors:** hallucinated_task, missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nl-196 (edge_noisy_long, en)
Edge tags: noisy, long_text, signature

**Input:** Hi team,

Thanks for attending yesterday's meeting. Here's a quick recap:

- Q1 revenue up 15% YoY
- Marketing costs have been optimized
- R&D is exploring new features

Action item: Rachel, please re...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Review design document" | Rachel | 2026-04-09 | pri=None
  - P: "Review design document" | Rachel | 2026-04-09 | pri=null
  - P: "Notify 1 day in advance for WFH policy" | null | null | pri=null

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-150 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-28]
Jack, please submit the meeting minutes by Friday.

[Email 2 — 2026-03-30]
Update: the meeting minutes is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Meeting minutes" | Jack | 2026-03-31 | pri=None
  - P: "submit meeting minutes" | Jack | 2026-04-01 | pri=medium
  - P: "submit meeting minutes" | Jack | 2026-03-31 | pri=medium

**Errors:** hallucinated_task, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### pr-217 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** Nhờ Hồ Quang Huy nộp bản đánh giá nhân sự trước thứ Sáu. Không gấp lắm, làm khi rảnh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Nộp bản đánh giá nhân sự" | Hồ Quang Huy | 2026-04-10 | pri=low
  - P: "nộp bản đánh giá nhân sự" | Hồ Quang Huy | null | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-209 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** [GẤP] Phạm Hương ơi, gửi wireframe trang chủ trước ngày mai. Rất gấp!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Gửi wireframe trang chủ" | Phạm Hương | 2026-04-01 | pri=high
  - P: "gửi wireframe trang chủ" | Phạm Hương | 2026-03-31 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-132 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-10

Tham dự: Đỗ Văn Hải, Phan Đức Anh

Action items:
- Đỗ Văn Hải: bản đánh giá nhân sự trước thứ Sáu
- Phan Đức Anh: file mockup UI trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Bản đánh giá nhân sự" | Đỗ Văn Hải | 2026-04-10 | pri=None
  - E: "File mockup UI" | Phan Đức Anh | 2026-04-10 | pri=None
  - P: "bản đánh giá nhân sự trước thứ Sáu" | Đỗ Văn Hải | 2026-04-08 | pri=null
  - P: "file mockup UI trước thứ Sáu" | Phan Đức Anh | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-202 (edge_forwarded, en)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-03-30
Subject: Assignment

Please ask Diana to send the financial spreadsheet by Friday.

---------- End forwarded -------...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send financial spreadsheet" | Diana | 2026-04-03 | pri=None
  - P: "send financial spreadsheet" | Diana | 2026-04-01 | pri=low

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-092 (email_ambiguous, vi)

**Input:** Phan xử lý bản đánh giá nhân sự sớm nhất có thể nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị bản đánh giá nhân sự" | Phan | None | pri=None
  - P: "Phan xử lý bản đánh giá nhân sự sớm nhất có thể" | None | None | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nl-194 (edge_noisy_long, en)
Edge tags: noisy, long_text, signature

**Input:** Hi team,

Thanks for attending yesterday's meeting. Here's a quick recap:

- Q1 revenue up 15% YoY
- Marketing costs have been optimized
- R&D is exploring new features

Action item: Karen, please sen...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Send partnership proposal" | Karen | 2026-04-05 | pri=None
  - P: "Send partnership proposal" | Karen | 2026-04-05 | pri=high
  - P: "Notify 1 day in advance for WFH" | None | None | pri=None

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-134 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-12

Tham dự: Lý Hoàng Long, Ngô Thanh Tùng

Action items:
- Lý Hoàng Long: wireframe trang chủ trước thứ Sáu
- Ngô Thanh Tùng: bản kế hoạch dự án trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Lý Hoàng Long | 2026-04-17 | pri=None
  - E: "Bản kế hoạch dự án" | Ngô Thanh Tùng | 2026-04-17 | pri=None
  - P: "wireframe trang chủ trước thứ Sáu" | Lý Hoàng Long | 2026-04-08 | pri=null
  - P: "bản kế hoạch dự án trước thứ Sáu" | Ngô Thanh Tùng | 2026-04-08 | pri=null

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}


_...and 72 more error samples (see JSON for full details)._


## 7. Summary Statistics

- Fully correct samples: **128/250** (51.2%)
- Samples with errors: **122/250** (48.8%)