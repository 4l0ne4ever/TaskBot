# Evaluation Report: pipeline

Generated: 2026-05-16T19:48:56
Dataset: 250 samples, 17 categories
Errors (runtime): 2 (other=2)

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9960 | 0.9228 | 0.9580 |
| Assignee | 1.0000 | 0.9198 | 0.9583 |
| Conflict | 1.0000 | 0.6000 | 0.7500 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.8099 |
| Deadline Near (+-1d) | 0.8306 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | 1.0 |
| False answer (GT empty) | 0.0 |
| False abstain (GT nonempty) | 0.0619 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.6,0.8) | 1 | 1.0000 |
| [0.8,1.0) | 250 | 1.0000 |

ECE (vs bin midpoint): **0.1008** (n=251 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.6667 | 0.6667 | 0.4000 | 0.4000 | 0.5714 |
| conflict_deadline | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.8462 |
| doc_meeting_notes | 15 | 0.8966 | 0.8966 | 0.5625 | 0.5625 | 0.0000 |
| doc_simple | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_forwarded | 8 | 1.0000 | 1.0000 | 0.8750 | 0.8750 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 1.0000 | 0.8000 | 0.9000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 1.0000 | 0.8571 | 0.8571 | 0.0000 |
| edge_noisy_long | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 1.0000 | 0.3000 | 0.6000 | 0.0000 |
| edge_special_format | 10 | 0.9474 | 0.9474 | 0.8000 | 0.8000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.8649 | 0.8889 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 0.9744 | 0.9744 | 0.9500 | 0.9500 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 1.0000 | 1.0000 | 0.7667 | 0.8000 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 0.9000 | 0.9000 | 0.0000 |
| missing_deadline | 10 | 0.9474 | 0.9474 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8125**
- Edge case categories weighted Title F1: **0.7782**
- Delta: **-0.0343**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 29 | 11.6% |
| missed_task | 14 | 5.6% |
| missed_assignee | 14 | 5.6% |
| complete_miss | 13 | 5.2% |
| missed_conflict | 10 | 4.0% |
| deadline_off_by_one | 5 | 2.0% |
| hallucinated_task | 1 | 0.4% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|
| conflict_assignee | 5 | 0 | 0 | 5 | 6 | 5 | 6 |
| conflict_deadline | 0 | 0 | 0 | 0 | 4 | 0 | 0 |
| doc_meeting_notes | 2 | 0 | 0 | 2 | 0 | 2 | 6 |
| edge_forwarded | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| edge_mixed_lang | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| edge_nickname | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 0 | 4 |
| edge_special_format | 1 | 0 | 0 | 1 | 0 | 1 | 2 |
| email_ambiguous | 3 | 0 | 1 | 4 | 0 | 4 | 0 |
| email_multi_task | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| email_simple | 0 | 1 | 0 | 0 | 0 | 0 | 6 |
| missing_assignee | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| missing_deadline | 1 | 0 | 0 | 1 | 0 | 1 | 0 |

## 6. Sample-Level Details (Errors Only)

### ac-157 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Wireframe trang chủ" | Lê Minh Đức | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-025 (email_simple, vi)

**Input:** @Nguyễn — chuẩn bị tài liệu thiết kế trước thứ Sáu này. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị tài liệu thiết kế" | Nguyễn | 2026-04-10 | pri=None
  - P: "chuẩn bị tài liệu thiết kế" | Nguyễn | None | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-153 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lê Minh Đức phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đặng Tuấn Kiệt phụ trách bản đánh giá nhân sự thay Lê Minh Đức.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "complete the API documentation" | Frankie | 2026-04-17 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "update Q1 report" | Hoàng | 2026-04-10 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-094 (email_ambiguous, en)

**Input:** Could Steve work on the API documentation sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Submit API documentation" | Steve | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-126 (doc_meeting_notes, en)

**Input:** Meeting Notes — 2026-04-04

Attendees: Henry, Ivy

Action items:
- Henry: API documentation by Friday
- Ivy: homepage wireframe by Friday

**Expected tasks:** 2 | **Predicted:** 2
  - E: "API documentation" | Henry | 2026-04-10 | pri=None
  - E: "Homepage wireframe" | Ivy | 2026-04-10 | pri=None
  - P: "API documentation" | Henry | 2026-04-17 | pri=None
  - P: "homepage wireframe" | Ivy | 2026-04-17 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-216 (edge_priority, en)
Edge tags: explicit_priority

**Input:** [URGENT] Paul, please update the API documentation by tomorrow. This is critical!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update API documentation" | Paul | 2026-04-08 | pri=high
  - P: "Update the API documentation" | Paul | 2026-04-07 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-139 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-31]
Karen, please submit the test results by Friday.

[Email 2 — 2026-04-02]
Update: the test results is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Test results" | Karen | 2026-04-03 | pri=None
  - P: "Submit test results" | Karen | 2026-04-03 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### pr-211 (edge_priority, en)
Edge tags: explicit_priority

**Input:** High priority: Steve, prepare the design document within 2 days.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Prepare design document" | Steve | 2026-04-04 | pri=high
  - P: "prepare the design document" | Steve | 2026-04-03 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-125 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-03

Tham dự: Hoàng Nam, Dương Thị Mai

Action items:
- Hoàng Nam: bản kế hoạch dự án trước thứ Sáu
- Dương Thị Mai: bản đánh giá nhân sự trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Bản kế hoạch dự án" | Hoàng Nam | 2026-04-03 | pri=None
  - E: "Bản đánh giá nhân sự" | Dương Thị Mai | 2026-04-03 | pri=None
  - P: "bản kế hoạch dự án" | Hoàng Nam | None | pri=None
  - P: "bản đánh giá nhân sự" | Dương Thị Mai | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-009 (email_simple, vi)

**Input:** Chào team,

Nhờ Vũ Thảo review bảng số liệu tài chính trước tuần tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review bảng số liệu tài chính" | Vũ Thảo | 2026-04-13 | pri=None
  - P: "review bảng số liệu tài chính" | Vũ Thảo | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-007 (email_simple, en)

**Input:** Hi team,

Please ask Tina to review the March report by end of month. Thanks.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Tina | 2026-04-30 | pri=None
  - P: "Review the March report" | Tina | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-188 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Hi Phạm Hương, nhờ bạn review cái March report trước tuần tới. Cảm ơn nha.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Phạm Hương | 2026-04-13 | pri=None
  - P: "review cái March report" | Phạm Hương | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-158 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lý Hoàng Long phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đỗ Văn Hải phụ trách wireframe trang chủ thay Lý Hoàng Long.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Wireframe trang chủ" | Đỗ Văn Hải | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### pr-217 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** Nhờ Hồ Quang Huy nộp bản đánh giá nhân sự trước thứ Sáu. Không gấp lắm, làm khi rảnh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Nộp bản đánh giá nhân sự" | Hồ Quang Huy | 2026-04-10 | pri=low
  - P: "Nộp bản đánh giá nhân sự" | Hồ Quang Huy | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-209 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** [GẤP] Phạm Hương ơi, gửi wireframe trang chủ trước ngày mai. Rất gấp!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Gửi wireframe trang chủ" | Phạm Hương | 2026-04-01 | pri=high
  - P: "gửi wireframe trang chủ" | Phạm Hương | 2026-03-31 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-134 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-12

Tham dự: Lý Hoàng Long, Ngô Thanh Tùng

Action items:
- Lý Hoàng Long: wireframe trang chủ trước thứ Sáu
- Ngô Thanh Tùng: bản kế hoạch dự án trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Lý Hoàng Long | 2026-04-17 | pri=None
  - E: "Bản kế hoạch dự án" | Ngô Thanh Tùng | 2026-04-17 | pri=None
  - P: "wireframe trang chủ" | Lý Hoàng Long | None | pri=None
  - P: "bản kế hoạch dự án" | Ngô Thanh Tùng | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-218 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** URGENT: Nguyễn cập nhật wireframe trang chủ ngay hôm nay nếu được.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Cập nhật wireframe trang chủ" | Nguyễn | 2026-04-10 | pri=high
  - P: "cập nhật wireframe trang chủ" | Nguyễn | 2026-04-08 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-014 (email_simple, vi)

**Input:** Gửi Vũ,

Phiền bạn chuẩn bị slide thuyết trình trước ngày 10 tháng 4.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị slide thuyết trình" | Vũ | 2026-04-10 | pri=None
  - P: "Chuẩn bị slide thuyết trình" | Vũ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-122 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-03-31

Tham dự: Trần Thị Bình, Lý Hoàng Long, Phạm Hương

Action items:
- Trần Thị Bình: hợp đồng NDA trước thứ Sáu
- Lý Hoàng Long: bảng số liệu tài chính trước thứ Sáu
- Phạm ...

**Expected tasks:** 3 | **Predicted:** 0
  - E: "Hợp đồng NDA" | Trần Thị Bình | 2026-04-03 | pri=None
  - E: "Bảng số liệu tài chính" | Lý Hoàng Long | 2026-04-03 | pri=None
  - E: "Bản kế hoạch dự án" | Phạm Hương | 2026-04-03 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 3}, assignee={'tp': 0, 'fp': 0, 'fn': 3}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-162 (missing_deadline, vi)

**Input:** Bùi Lan Anh ơi, chỉnh sửa kết quả kiểm thử giúp mình nhé.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chỉnh sửa kết quả kiểm thử" | Bùi Lan Anh | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-234 (edge_special_format, vi)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Phạm Hương] tài liệu thiết kế (DL: thứ Sáu)
* [Huỳnh Minh Tâm] file mockup UI (DL: thứ Sáu)
* [DONE] Triển khai API endpoint

**Expected tasks:** 2 | **Predicted:** 0
  - E: "Tài liệu thiết kế" | Phạm Hương | 2026-04-03 | pri=None
  - E: "File mockup UI" | Huỳnh Minh Tâm | 2026-04-03 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-146 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-07]
Nguyễn Văn An, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-09]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None
  - P: "nộp bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-010 (email_simple, vi)

**Input:** Anh/chị Lê ơi, nhờ cập nhật kết quả kiểm thử trước tuần tới ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-13 | pri=None
  - P: "cập nhật kết quả kiểm thử" | Lê | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-130 (doc_meeting_notes, en)

**Input:** Meeting Notes — 2026-04-08

Attendees: Diana, Olivia

Action items:
- Diana: performance review by Friday
- Olivia: project plan by Friday

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Performance review" | Diana | 2026-04-10 | pri=None
  - E: "Project plan" | Olivia | 2026-04-10 | pri=None
  - P: "performance review" | Diana | None | pri=None
  - P: "project plan" | Olivia | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-239 (edge_special_format, vi)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Phan Đức Anh] slide thuyết trình (DL: thứ Sáu)
* [Trần Thị Bình] bản đánh giá nhân sự (DL: thứ Sáu)
* [DONE] Triển khai API endpoint

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Slide thuyết trình" | Phan Đức Anh | 2026-04-10 | pri=None
  - E: "Bản đánh giá nhân sự" | Trần Thị Bình | 2026-04-10 | pri=None
  - P: "slide thuyết trình" | Phan Đức Anh | None | pri=None
  - P: "bản đánh giá nhân sự" | Trần Thị Bình | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-015 (email_simple, en)

**Input:** Quick reminder: Eve, presentation slides is due by next Friday. Please draft it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Draft presentation slides" | Eve | 2026-04-10 | pri=None
  - P: "Draft presentation slides" | Eve | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-039 (email_multi_task, vi)
Edge tags: 3_tasks

**Input:** Chào team,

1. Huỳnh Minh Tâm: nộp hợp đồng NDA trong 7 ngày.
2. Hoàng Nam: review bản kế hoạch dự án trong 7 ngày.
3. Nguyễn Văn An: hoàn thành slide thuyết trình trong 2 ngày.

Cảm ơn mọi người.

**Expected tasks:** 3 | **Predicted:** 0
  - E: "Nộp hợp đồng NDA" | Huỳnh Minh Tâm | 2026-04-14 | pri=None
  - E: "Review bản kế hoạch dự án" | Hoàng Nam | 2026-04-14 | pri=None
  - E: "Hoàn thành slide thuyết trình" | Nguyễn Văn An | 2026-04-09 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 3}, assignee={'tp': 0, 'fp': 0, 'fn': 3}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-171 (missing_assignee, vi)

**Input:** Ai đó hoàn thành hợp đồng NDA trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành hợp đồng NDA" | None | 2026-04-03 | pri=None
  - P: "hoàn thành hợp đồng NDA" | None | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-083 (email_ambiguous, en)

**Input:** Tina — try to get the meeting minutes done as soon as possible.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit meeting minutes" | Tina | None | pri=None
  - P: "try to get the meeting minutes done" | Tina | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-127 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-05

Tham dự: Lý Hoàng Long, Phạm Hương, Phan Đức Anh

Action items:
- Lý Hoàng Long: tài liệu thiết kế trước thứ Sáu
- Phạm Hương: biên bản họp trước thứ Sáu
- Phan Đức Anh: ...

**Expected tasks:** 3 | **Predicted:** 0
  - E: "Tài liệu thiết kế" | Lý Hoàng Long | 2026-04-10 | pri=None
  - E: "Biên bản họp" | Phạm Hương | 2026-04-10 | pri=None
  - E: "Bảng số liệu tài chính" | Phan Đức Anh | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 3}, assignee={'tp': 0, 'fp': 0, 'fn': 3}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-155 (conflict_assignee, en)

**Input:** Email thread:

[Email 1]
Paul is responsible for the partnership proposal, due Friday.

[Email 2]
Update: Henry will take over the partnership proposal from Paul.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Partnership proposal" | Henry | 2026-04-03 | pri=None
  - P: "partnership proposal" | Henry | None | pri=None

**Errors:** wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### dc-136 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-28]
Frank, please submit the March report by Friday.

[Email 2 — 2026-03-30]
Update: the March report is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "March report" | Frank | 2026-03-31 | pri=None
  - P: "Submit the March report" | Frank | 2026-03-31 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### pr-215 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** [GẤP] Lê Minh Đức ơi, dịch kết quả kiểm thử trước ngày mai. Rất gấp!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Dịch kết quả kiểm thử" | Lê Minh Đức | 2026-04-08 | pri=high
  - P: "dịch kết quả kiểm thử" | Lê Minh Đức | 2026-04-06 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-151 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách bảng số liệu tài chính, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Trần Thị Bình phụ trách bảng số liệu tài chính thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Bảng số liệu tài chính" | Trần Thị Bình | 2026-04-03 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### ac-159 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách biên bản họp, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lý Hoàng Long phụ trách biên bản họp thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Biên bản họp" | Lý Hoàng Long | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### fw-206 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-03
Subject: Phân công

Nhờ Phan Đức Anh viết báo cáo Q1 trước thứ Sáu.

---------- End forwarded ----------

FYI team, ...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết báo cáo Q1" | Phan Đức Anh | 2026-04-10 | pri=None
  - P: "Viết báo cáo Q1" | Phan Đức Anh | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-006 (email_simple, vi)

**Input:** Chào team,

Nhờ Đặng Tuấn Kiệt chỉnh sửa tài liệu thiết kế trước thứ Sáu tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Đặng Tuấn Kiệt | 2026-04-17 | pri=None
  - P: "chỉnh sửa tài liệu thiết kế" | Đặng Tuấn Kiệt | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-081 (email_ambiguous, en)

**Input:** Could Henry work on the partnership proposal sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Prepare partnership proposal" | Henry | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-091 (email_ambiguous, en)

**Input:** Could Diana work on the March report sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Submit March report" | Diana | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-214 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** Nhờ Nguyễn Văn An review tài liệu API docs trước thứ Sáu. Không gấp lắm, làm khi rảnh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review tài liệu API docs" | Nguyễn Văn An | 2026-04-05 | pri=low
  - P: "review tài liệu API docs" | Nguyễn Văn An | 2026-04-17 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-144 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-05]
Olivia, please submit the test results by Friday.

[Email 2 — 2026-04-07]
Update: the test results is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Test results" | Olivia | 2026-04-08 | pri=None
  - P: "submit the test results" | Olivia | 2026-04-08 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}


## 7. Summary Statistics

- Fully correct samples: **207/250** (82.8%)
- Samples with errors: **43/250** (17.2%)