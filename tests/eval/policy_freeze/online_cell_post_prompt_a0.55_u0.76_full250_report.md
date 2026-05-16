# Evaluation Report: pipeline

Generated: 2026-05-13T10:26:08
Dataset: 168 samples, 17 categories
Errors (runtime): 5 (other=2, daily_quota=2, rate_limit_other=1)

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9780 | 0.9622 | 0.9700 |
| Assignee | 1.0000 | 0.9492 | 0.9739 |
| Conflict | 1.0000 | 0.6471 | 0.7857 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.7500 |
| Deadline Near (+-1d) | 0.7679 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | 1.0 |
| False answer (GT empty) | 0.0 |
| False abstain (GT nonempty) | 0.0496 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.6,0.8) | 4 | 1.0000 |
| [0.8,1.0) | 174 | 1.0000 |

ECE (vs bin midpoint): **0.1045** (n=178 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 7 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| conflict_deadline | 10 | 0.6667 | 0.6667 | 0.4000 | 0.4000 | 0.5714 |
| doc_meeting_notes | 11 | 1.0000 | 1.0000 | 0.8261 | 0.8261 | 0.0000 |
| doc_simple | 12 | 0.9565 | 0.9565 | 0.9167 | 0.9167 | 0.0000 |
| edge_forwarded | 5 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_mixed_lang | 5 | 1.0000 | 1.0000 | 0.2000 | 0.2000 | 0.0000 |
| edge_nickname | 6 | 1.0000 | 1.0000 | 0.6667 | 0.6667 | 0.0000 |
| edge_noisy_long | 7 | 0.9231 | 0.9231 | 0.8571 | 0.8571 | 0.0000 |
| edge_priority | 8 | 1.0000 | 1.0000 | 0.3750 | 0.7500 | 0.0000 |
| edge_special_format | 8 | 1.0000 | 1.0000 | 0.8750 | 0.8750 | 0.0000 |
| edge_tricky_negative | 9 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 12 | 0.9565 | 0.9565 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 17 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 18 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 20 | 0.9744 | 0.9744 | 0.6000 | 0.6000 | 0.0000 |
| missing_assignee | 8 | 1.0000 | 0.0000 | 0.7500 | 0.7500 | 0.0000 |
| missing_deadline | 5 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8093**
- Edge case categories weighted Title F1: **0.8013**
- Delta: **-0.0080**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 36 | 21.4% |
| missed_assignee | 9 | 5.4% |
| missed_task | 7 | 4.2% |
| complete_miss | 7 | 4.2% |
| missed_conflict | 6 | 3.6% |
| hallucinated_task | 4 | 2.4% |
| deadline_off_by_one | 3 | 1.8% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| conflict_deadline | 3 | 0 | 4 | 5 | 6 | 3 | 6 |
| doc_meeting_notes | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| doc_simple | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| edge_mixed_lang | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| edge_nickname | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| edge_noisy_long | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| edge_priority | 0 | 3 | 0 | 0 | 0 | 0 | 2 |
| edge_special_format | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| email_ambiguous | 1 | 0 | 0 | 1 | 0 | 1 | 0 |
| email_simple | 1 | 0 | 0 | 1 | 0 | 1 | 8 |
| missing_assignee | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

## 6. Sample-Level Details (Errors Only)

### mx-189 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Đỗ | 2026-04-10 | pri=None
  - P: "update NDA contract asap" | Đỗ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "wireframe trang chủ" | Lê Minh Đức | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nn-246 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Mai ơi, soạn hợp đồng NDA trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Soạn hợp đồng NDA" | Mai | 2026-04-03 | pri=None
  - P: "soạn hợp đồng NDA" | Mai | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-025 (email_simple, vi)

**Input:** @Nguyễn — chuẩn bị tài liệu thiết kế trước thứ Sáu này. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị tài liệu thiết kế" | Nguyễn | 2026-04-10 | pri=None
  - P: "chuẩn bị tài liệu thiết kế" | Nguyễn | None | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "Nộp tài liệu thiết kế" | None | 2026-04-02 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-141 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-02]
Bob, please submit the partnership proposal by Friday.

[Email 2 — 2026-04-04]
Update: the partnership proposal is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Partnership proposal" | Bob | 2026-04-05 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

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

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None
  - P: "báo cáo tháng 3" | Phạm Hương | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### pr-216 (edge_priority, en)
Edge tags: explicit_priority

**Input:** [URGENT] Paul, please update the API documentation by tomorrow. This is critical!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update API documentation" | Paul | 2026-04-08 | pri=high
  - P: "update the API documentation" | Paul | 2026-04-07 | pri=None

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

### eval-179 (missing_assignee, vi)

**Input:** Ai đó hoàn thành hợp đồng NDA trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành hợp đồng NDA" | None | 2026-04-10 | pri=None
  - P: "hoàn thành hợp đồng NDA" | None | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-012 (email_simple, vi)

**Input:** Gửi Hồ,

Phiền bạn dịch file mockup UI trước cuối tháng.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Dịch file mockup UI" | Hồ | 2026-04-30 | pri=None
  - P: "dịch file mockup UI" | Hồ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

### eval-176 (missing_assignee, vi)

**Input:** Task: báo cáo tháng 3 — deadline thứ Sáu. Chưa assign.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo tháng 3" | None | 2026-04-10 | pri=None
  - P: "báo cáo tháng 3" | None | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-017 (email_simple, en)

**Input:** Hey Karen,

Could you send the project plan by next Friday? Appreciate it.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Send project plan" | Karen | 2026-04-10 | pri=None
  - P: "send the project plan" | Karen | None | pri=None

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

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Wireframe trang chủ" | Phan Đức Anh | 2026-04-04 | pri=None
  - P: "nộp wireframe trang chủ" | None | 2026-04-04 | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### ac-154 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Dương Thị Mai phụ trách kết quả kiểm thử, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Hoàng Nam phụ trách kết quả kiểm thử thay Dương Thị Mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Kết quả kiểm thử" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "phụ trách kết quả kiểm thử" | Hoàng Nam | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### nl-200 (edge_noisy_long, vi)
Edge tags: noisy, long_text, signature

**Input:** Chào team,

Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:

- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái
- Chi phí marketing đã được tối ưu
- Nhóm R&D đang nghi...

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Cập nhật bản đánh giá nhân sự" | Huỳnh Minh Tâm | 2026-04-13 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-013 (email_simple, vi)

**Input:** @Phạm Hương — dịch biên bản họp trước ngày 10 tháng 4. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Dịch biên bản họp" | Phạm Hương | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-142 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-03]
Trần Thị Bình, tài liệu API docs nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-05]
Cập nhật: tài liệu API docs cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu API docs" | Trần Thị Bình | 2026-04-06 | pri=None
  - P: "Nộp tài liệu API docs" | Trần Thị Bình | 2026-04-10 | pri=None
  - P: "Nộp tài liệu API docs" | None | 2026-04-06 | pri=None

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### eval-009 (email_simple, vi)

**Input:** Chào team,

Nhờ Vũ Thảo review bảng số liệu tài chính trước tuần tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review bảng số liệu tài chính" | Vũ Thảo | 2026-04-13 | pri=None
  - P: "review bảng số liệu tài chính" | Vũ Thảo | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-188 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Hi Phạm Hương, nhờ bạn review cái March report trước tuần tới. Cảm ơn nha.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review March report" | Phạm Hương | 2026-04-13 | pri=None
  - P: "review cái March report" | Phạm Hương | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-187 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update project plan asap, deadline là trước cuối tháng.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update project plan" | Đỗ | 2026-04-30 | pri=None
  - P: "update project plan" | Đỗ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-158 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lý Hoàng Long phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đỗ Văn Hải phụ trách wireframe trang chủ thay Lý Hoàng Long.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Wireframe trang chủ" | Đỗ Văn Hải | 2026-04-10 | pri=None
  - P: "phụ trách wireframe trang chủ" | Đỗ Văn Hải | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 1, 'fp': 0, 'fn': 0}

### dc-150 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-03-28]
Jack, please submit the meeting minutes by Friday.

[Email 2 — 2026-03-30]
Update: the meeting minutes is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Meeting minutes" | Jack | 2026-03-31 | pri=None
  - P: "submit the meeting minutes" | Jack | None | pri=None
  - P: "submit the meeting minutes" | None | 2026-03-31 | pri=None

**Errors:** hallucinated_task, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

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
  - P: "bản đánh giá nhân sự" | Đỗ Văn Hải | None | pri=None
  - P: "file mockup UI" | Phan Đức Anh | None | pri=None

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

### nn-244 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Lan ơi, tổng hợp proposal hợp tác trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tổng hợp proposal hợp tác" | Lan | 2026-04-03 | pri=None
  - P: "tổng hợp proposal hợp tác" | Lan | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-234 (edge_special_format, vi)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Phạm Hương] tài liệu thiết kế (DL: thứ Sáu)
* [Huỳnh Minh Tâm] file mockup UI (DL: thứ Sáu)
* [DONE] Triển khai API endpoint

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Phạm Hương | 2026-04-03 | pri=None
  - E: "File mockup UI" | Huỳnh Minh Tâm | 2026-04-03 | pri=None
  - P: "tài liệu thiết kế" | Phạm Hương | None | pri=None
  - P: "file mockup UI" | Huỳnh Minh Tâm | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-146 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-07]
Nguyễn Văn An, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-09]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Bảng số liệu tài chính" | Nguyễn Văn An | 2026-04-10 | pri=None
  - P: "nộp bảng số liệu tài chính" | Nguyễn Văn An | None | pri=None
  - P: "nộp bảng số liệu tài chính" | None | 2026-04-10 | pri=None

**Errors:** hallucinated_task, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-010 (email_simple, vi)

**Input:** Anh/chị Lê ơi, nhờ cập nhật kết quả kiểm thử trước tuần tới ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-13 | pri=None
  - P: "cập nhật kết quả kiểm thử" | Lê | None | pri=None

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
  - P: "Take over the design document" | Olivia | None | pri=None

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

### eval-115 (doc_simple, vi)

**Input:** PHÂN CÔNG CÔNG VIỆC

- Nhân viên: Vũ Thảo
- Nhiệm vụ: slide thuyết trình
- Deadline: 02/04/2026

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Slide thuyết trình" | Vũ Thảo | 2026-04-02 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-149 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-10]
Lý, bảng số liệu tài chính nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-12]
Cập nhật: bảng số liệu tài chính cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Bảng số liệu tài chính" | Lý | 2026-04-13 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### dc-145 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-06]
Hồ, tài liệu API docs nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-08]
Cập nhật: tài liệu API docs cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Tài liệu API docs" | Hồ | 2026-04-09 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}


## 7. Summary Statistics

- Fully correct samples: **125/168** (74.4%)
- Samples with errors: **43/168** (25.6%)