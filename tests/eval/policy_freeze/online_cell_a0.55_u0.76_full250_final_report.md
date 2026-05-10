# Evaluation Report: pipeline

Generated: 2026-05-10T12:09:42
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9782 | 0.9890 | 0.9835 |
| Assignee | 0.9960 | 0.9427 | 0.9686 |
| Conflict | 1.0000 | 0.8000 | 0.8889 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.8595 |
| Deadline Near (+-1d) | 0.9008 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | 1.0 |
| False answer (GT empty) | 0.0 |
| False abstain (GT nonempty) | 0.0143 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.6,0.8) | 11 | 1.0000 |
| [0.8,1.0) | 258 | 1.0000 |

ECE (vs bin midpoint): **0.1082** (n=269 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.9524 | 0.9000 | 0.1000 | 0.1000 | 0.9474 |
| conflict_deadline | 15 | 0.8571 | 0.5000 | 0.8000 | 1.0000 | 0.8462 |
| doc_meeting_notes | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| doc_simple | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_forwarded | 8 | 1.0000 | 1.0000 | 0.8750 | 1.0000 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 1.0000 | 0.5000 | 0.7000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_noisy_long | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 1.0000 | 0.4000 | 0.7000 | 0.0000 |
| edge_special_format | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.9189 | 0.9189 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 1.0000 | 0.9831 | 0.6667 | 0.7000 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| missing_deadline | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8375**
- Edge case categories weighted Title F1: **0.7857**
- Delta: **-0.0518**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 24 | 9.6% |
| missed_assignee | 15 | 6.0% |
| deadline_off_by_one | 10 | 4.0% |
| hallucinated_task | 6 | 2.4% |
| missed_conflict | 5 | 2.0% |
| missed_task | 3 | 1.2% |
| complete_miss | 3 | 1.2% |
| wrong_assignee | 1 | 0.4% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_assignee | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 9 |
| conflict_deadline | 0 | 3 | 5 | 10 | 4 | 0 | 0 | 0 |
| edge_forwarded | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| edge_mixed_lang | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 3 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| email_ambiguous | 3 | 0 | 0 | 3 | 0 | 3 | 0 | 0 |
| email_simple | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 9 |

## 6. Sample-Level Details (Errors Only)

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None
  - P: "hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-03 | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-157 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Wireframe trang chủ" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "Wireframe trang chủ" | Lê Minh Đức | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "nộp tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-03 | pri=None
  - P: "nộp tài liệu thiết kế" | None | 2026-04-02 | pri=None

**Errors:** hallucinated_task, deadline_off_by_one, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### dc-141 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-02]
Bob, please submit the partnership proposal by Friday.

[Email 2 — 2026-04-04]
Update: the partnership proposal is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Partnership proposal" | Bob | 2026-04-05 | pri=None
  - P: "Submit partnership proposal" | None | 2026-04-05 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-153 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lê Minh Đức phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đặng Tuấn Kiệt phụ trách bản đánh giá nhân sự thay Lê Minh Đức.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None
  - P: "bản đánh giá nhân sự" | Đặng Tuấn Kiệt | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "update Q1 report" | Hoàng | 2026-04-03 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hợp đồng NDA" | Nguyễn | 2026-04-07 | pri=None
  - P: "nộp hợp đồng NDA" | None | 2026-04-07 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None
  - P: "Báo cáo tháng 3" | Phạm Hương | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### mx-184 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Phan Đức Anh: update March report asap, deadline là trước 15/4.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update March report" | Phan Đức Anh | 2026-04-15 | pri=None
  - P: "update March report" | Phan Đức Anh | 2026-04-14 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Submit the test results" | Karen | 2026-04-03 | pri=None
  - P: "Submit the test results" | None | 2026-04-03 | pri=None

**Errors:** hallucinated_task, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-017 (email_simple, en)

**Input:** Hey Karen,

Could you send the project plan by next Friday? Appreciate it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send project plan" | Karen | 2026-04-10 | pri=None
  - P: "Send the project plan" | Karen | 2026-04-03 | pri=None

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

### dc-140 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-01]
Phan Đức Anh, wireframe trang chủ nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-03]
Cập nhật: wireframe trang chủ cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Phan Đức Anh | 2026-04-04 | pri=None
  - P: "Nộp wireframe trang chủ" | Phan Đức Anh | 2026-04-03 | pri=None
  - P: "Nộp wireframe trang chủ" | None | 2026-04-04 | pri=None

**Errors:** hallucinated_task, deadline_off_by_one, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### ac-154 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Dương Thị Mai phụ trách kết quả kiểm thử, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Hoàng Nam phụ trách kết quả kiểm thử thay Dương Thị Mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Kết quả kiểm thử" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "Hoàn thành kết quả kiểm thử" | Dương Thị Mai | 2026-04-03 | pri=None
  - P: "Hoàn thành kết quả kiểm thử" | Hoàng Nam | None | pri=None

**Errors:** hallucinated_task, missed_assignee, wrong_assignee, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-013 (email_simple, vi)

**Input:** @Phạm Hương — dịch biên bản họp trước ngày 10 tháng 4. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Dịch biên bản họp" | Phạm Hương | 2026-04-10 | pri=None
  - P: "dịch biên bản họp" | Phạm Hương | None | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-142 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-03]
Trần Thị Bình, tài liệu API docs nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-05]
Cập nhật: tài liệu API docs cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tài liệu API docs" | Trần Thị Bình | 2026-04-06 | pri=None
  - P: "Nộp tài liệu API docs" | None | 2026-04-06 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

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
  - P: "review cái March report" | Phạm Hương | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-158 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lý Hoàng Long phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đỗ Văn Hải phụ trách wireframe trang chủ thay Lý Hoàng Long.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Wireframe trang chủ" | Đỗ Văn Hải | 2026-04-10 | pri=None
  - P: "wireframe trang chủ" | Đỗ Văn Hải | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-150 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-28]
Jack, please submit the meeting minutes by Friday.

[Email 2 — 2026-03-30]
Update: the meeting minutes is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Meeting minutes" | Jack | 2026-03-31 | pri=None
  - P: "submit the meeting minutes" | None | 2026-03-31 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

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
  - P: "Chuẩn bị slide thuyết trình" | Vũ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-146 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-07]
Nguyễn Văn An, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-09]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None
  - P: "Nộp bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None
  - P: "Nộp bảng số liệu tài chính" | None | 2026-04-10 | pri=None

**Errors:** hallucinated_task, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### fw-204 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-01
Subject: Phân công

Nhờ Dương chỉnh sửa kết quả kiểm thử trước thứ Sáu.

---------- End forwarded ----------

FYI te...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa kết quả kiểm thử" | Dương | 2026-04-03 | pri=None
  - P: "chỉnh sửa kết quả kiểm thử" | Dương | 2026-04-02 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-010 (email_simple, vi)

**Input:** Anh/chị Lê ơi, nhờ cập nhật kết quả kiểm thử trước tuần tới ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-13 | pri=None
  - P: "cập nhật kết quả kiểm thử" | Lê | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-015 (email_simple, en)

**Input:** Quick reminder: Eve, presentation slides is due by next Friday. Please draft it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Draft presentation slides" | Eve | 2026-04-10 | pri=None
  - P: "Draft presentation slides" | Eve | 2026-04-03 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-152 (conflict_assignee, en)

**Input:** Email thread:

[Email 1]
Diana is responsible for the design document, due Friday.

[Email 2]
Update: Olivia will take over the design document from Diana.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Design document" | Olivia | 2026-04-03 | pri=None
  - P: "Design document" | Olivia | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-160 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Nguyễn Văn An phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Hoàng Nam phụ trách bản đánh giá nhân sự thay Nguyễn Văn An.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bản đánh giá nhân sự" | Hoàng Nam | 2026-04-10 | pri=None
  - P: "phụ trách bản đánh giá nhân sự" | Hoàng Nam | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-149 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-10]
Lý, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-12]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bảng số liệu tài chính" | Lý | 2026-04-13 | pri=None
  - P: "Nộp bảng số liệu tài chính" | None | 2026-04-13 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-145 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-06]
Hồ, tài liệu API docs nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-08]
Cập nhật: tài liệu API docs cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu API docs" | Hồ | 2026-04-09 | pri=None
  - P: "nộp tài liệu API docs" | Hồ | 2026-04-10 | pri=None
  - P: "nộp tài liệu API docs" | None | 2026-04-09 | pri=None

**Errors:** hallucinated_task, deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-155 (conflict_assignee, en)

**Input:** Email thread:

[Email 1]
Paul is responsible for the partnership proposal, due Friday.

[Email 2]
Update: Henry will take over the partnership proposal from Paul.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Partnership proposal" | Henry | 2026-04-03 | pri=None
  - P: "Partnership proposal" | Henry | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### mx-183 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Mọi người ơi, Hoàng Nam handle financial spreadsheet trước thứ Sáu tới. Let me know if any issues.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Handle financial spreadsheet" | Hoàng Nam | 2026-04-10 | pri=None
  - P: "handle financial spreadsheet" | Hoàng Nam | 2026-04-03 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-027 (email_simple, vi)

**Input:** Gửi Phan Đức Anh,

Phiền bạn review kết quả kiểm thử trước thứ Sáu tới.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review kết quả kiểm thử" | Phan Đức Anh | 2026-04-24 | pri=None
  - P: "review kết quả kiểm thử" | Phan Đức Anh | 2026-04-17 | pri=None

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
  - P: "Submit the March report" | None | 2026-03-31 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

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

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bảng số liệu tài chính" | Trần Thị Bình | 2026-04-03 | pri=None
  - P: "phụ trách bảng số liệu tài chính" | Trần Thị Bình | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-023 (email_simple, en)

**Input:** Grace — please finalize the project plan by next Friday.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Finalize project plan" | Grace | 2026-04-17 | pri=None
  - P: "finalize the project plan" | Grace | 2026-04-10 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-159 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách biên bản họp, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lý Hoàng Long phụ trách biên bản họp thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Biên bản họp" | Lý Hoàng Long | 2026-04-10 | pri=None
  - P: "Biên bản họp" | Lý Hoàng Long | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-006 (email_simple, vi)

**Input:** Chào team,

Nhờ Đặng Tuấn Kiệt chỉnh sửa tài liệu thiết kế trước thứ Sáu tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Đặng Tuấn Kiệt | 2026-04-17 | pri=None
  - P: "chỉnh sửa tài liệu thiết kế" | Đặng Tuấn Kiệt | 2026-04-10 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-182 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update NDA contract asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Hoàng | 2026-04-10 | pri=None
  - P: "update NDA contract" | Hoàng | 2026-04-03 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-147 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-08]
Hoàng Nam, proposal hợp tác nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-10]
Cập nhật: proposal hợp tác cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Proposal hợp tác" | Hoàng Nam | 2026-04-11 | pri=None
  - P: "Nộp proposal hợp tác" | None | 2026-04-11 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-148 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-09]
Paul, please submit the design document by Friday.

[Email 2 — 2026-04-11]
Update: the design document is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Design document" | Paul | 2026-04-12 | pri=None
  - P: "Submit the design document" | None | 2026-04-12 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

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
  - P: "Ask Tina to review the partnership proposal" | None | 2026-04-10 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "review tài liệu API docs" | Nguyễn Văn An | 2026-04-10 | pri=low

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
  - P: "Submit the test results" | None | 2026-04-08 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}


_...and 1 more error samples (see JSON for full details)._


## 7. Summary Statistics

- Fully correct samples: **199/250** (79.6%)
- Samples with errors: **51/250** (20.4%)