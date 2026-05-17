# Evaluation Report: pipeline

Generated: 2026-05-17T11:21:46
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9924 | 0.9559 | 0.9738 |
| Assignee | 1.0000 | 0.9504 | 0.9746 |
| Conflict | 1.0000 | 0.6400 | 0.7805 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.8802 |
| Deadline Near (+-1d) | 0.9050 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | 0.95 |
| False answer (GT empty) | 0.05 |
| False abstain (GT nonempty) | 0.0476 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.4,0.6) | 1 | 1.0000 |
| [0.6,0.8) | 1 | 1.0000 |
| [0.8,1.0) | 258 | 1.0000 |

ECE (vs bin midpoint): **0.1023** (n=260 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.7500 | 0.7500 | 0.6000 | 0.6000 | 0.7500 |
| conflict_deadline | 15 | 0.9286 | 0.9286 | 0.8667 | 0.8667 | 0.8000 |
| doc_meeting_notes | 15 | 1.0000 | 1.0000 | 0.8125 | 0.8125 | 0.0000 |
| doc_simple | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_forwarded | 8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 1.0000 | 0.7000 | 0.8000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_noisy_long | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 1.0000 | 0.4000 | 0.7000 | 0.0000 |
| edge_special_format | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.9189 | 0.9189 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 0.9744 | 0.9744 | 0.9500 | 0.9500 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 1.0000 | 0.9831 | 0.8333 | 0.9000 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| missing_deadline | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8287**
- Edge case categories weighted Title F1: **0.7857**
- Delta: **-0.0430**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 18 | 7.2% |
| missed_assignee | 11 | 4.4% |
| missed_task | 10 | 4.0% |
| complete_miss | 10 | 4.0% |
| missed_conflict | 9 | 3.6% |
| deadline_off_by_one | 6 | 2.4% |
| hallucinated_task | 2 | 0.8% |
| false_positive_extraction | 2 | 0.8% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | false_positive_extraction | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|
| conflict_assignee | 4 | 0 | 0 | 0 | 4 | 4 | 4 | 4 |
| conflict_deadline | 2 | 0 | 0 | 0 | 2 | 5 | 2 | 2 |
| doc_meeting_notes | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| edge_mixed_lang | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| edge_tricky_negative | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| email_ambiguous | 3 | 0 | 0 | 0 | 3 | 0 | 3 | 0 |
| email_multi_task | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 1 |
| email_no_task | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| email_simple | 0 | 2 | 0 | 0 | 1 | 0 | 0 | 3 |

## 6. Sample-Level Details (Errors Only)

### eval-036 (email_multi_task, vi)
Edge tags: 3_tasks

**Input:** Chào team,

1. Hồ Quang Huy: chỉnh sửa bản kế hoạch dự án trong 2 ngày.
2. Trần Thị Bình: chuẩn bị slide thuyết trình trong 3 ngày.
3. Huỳnh Minh Tâm: chỉnh sửa file mockup UI trong 5 ngày.

Cảm ơn mọ...

**Expected tasks:** 3 | **Predicted:** 0
  - E: "Chỉnh sửa bản kế hoạch dự án" | Hồ Quang Huy | 2026-04-06 | pri=None
  - E: "Chuẩn bị slide thuyết trình" | Trần Thị Bình | 2026-04-07 | pri=None
  - E: "Chỉnh sửa file mockup UI" | Huỳnh Minh Tâm | 2026-04-09 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 3}, assignee={'tp': 0, 'fp': 0, 'fn': 3}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "submit the test results" | Karen | 2026-04-03 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-133 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-11

Tham dự: Trần Thị Bình, Phạm Hương

Action items:
- Trần Thị Bình: hợp đồng NDA trước thứ Sáu
- Phạm Hương: báo cáo tháng 3 trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Hợp đồng NDA" | Trần Thị Bình | 2026-04-17 | pri=None
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-17 | pri=None
  - P: "hợp đồng NDA" | Trần Thị Bình | None | pri=None
  - P: "báo cáo tháng 3" | Phạm Hương | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-017 (email_simple, en)

**Input:** Hey Karen,

Could you send the project plan by next Friday? Appreciate it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send project plan" | Karen | 2026-04-10 | pri=None
  - P: "Send the project plan" | Karen | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-211 (edge_priority, en)
Edge tags: explicit_priority

**Input:** High priority: Steve, prepare the design document within 2 days.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Prepare design document" | Steve | 2026-04-04 | pri=high
  - P: "prepare the design document" | Steve | 2026-04-03 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-009 (email_simple, vi)

**Input:** Chào team,

Nhờ Vũ Thảo review bảng số liệu tài chính trước tuần tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review bảng số liệu tài chính" | Vũ Thảo | 2026-04-13 | pri=None
  - P: "review bảng số liệu tài chính" | Vũ Thảo | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-188 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Hi Phạm Hương, nhờ bạn review cái March report trước tuần tới. Cảm ơn nha.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Phạm Hương | 2026-04-13 | pri=None
  - P: "review March report" | Phạm Hương | 2026-04-12 | pri=None

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

### pr-209 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** [GẤP] Phạm Hương ơi, gửi wireframe trang chủ trước ngày mai. Rất gấp!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Gửi wireframe trang chủ" | Phạm Hương | 2026-04-01 | pri=high
  - P: "gửi wireframe trang chủ" | Phạm Hương | 2026-03-31 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Chuẩn bị slide thuyết trình" | Vũ | 2027-04-10 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-146 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-07]
Nguyễn Văn An, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-09]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-010 (email_simple, vi)

**Input:** Anh/chị Lê ơi, nhờ cập nhật kết quả kiểm thử trước tuần tới ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-13 | pri=None
  - P: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

### eval-066 (email_no_task, vi)

**Input:** Dưới đây là link tài liệu tham khảo: https://docs.google.com/xxx

Mọi người đọc qua nhé.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Đọc tài liệu tham khảo" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-186 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Mọi người ơi, Huỳnh Minh Tâm handle NDA contract trước thứ Sáu này. Let me know if any issues.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Handle NDA contract" | Huỳnh Minh Tâm | 2026-04-10 | pri=None
  - P: "handle NDA contract" | Huỳnh Minh Tâm | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

### tn-231 (edge_tricky_negative, vi)
Edge tags: tricky_negative, deferred

**Input:** Lưu ý: hợp đồng NDA chỉ cần làm khi phase 2 bắt đầu (chưa xác định).

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Làm hợp đồng NDA" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-147 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-08]
Hoàng Nam, proposal hợp tác nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-10]
Cập nhật: proposal hợp tác cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Proposal hợp tác" | Hoàng Nam | 2026-04-11 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-081 (email_ambiguous, en)

**Input:** Could Henry work on the partnership proposal sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Prepare partnership proposal" | Henry | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-020 (email_simple, en)

**Input:** Hi team,

Please ask Tina to review the partnership proposal by this Friday. Thanks.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review partnership proposal" | Tina | 2026-04-10 | pri=None
  - P: "Ask Tina to review the partnership proposal" | None | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "review tài liệu API docs" | Nguyễn Văn An | 2026-04-10 | pri=None

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
  - P: "Submit the test results" | Olivia | 2026-04-08 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}


## 7. Summary Statistics

- Fully correct samples: **218/250** (87.2%)
- Samples with errors: **32/250** (12.8%)