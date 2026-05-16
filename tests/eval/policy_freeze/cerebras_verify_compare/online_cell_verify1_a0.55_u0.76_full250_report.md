# Evaluation Report: pipeline

Generated: 2026-05-15T23:15:59
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9959 | 0.9007 | 0.9459 |
| Assignee | 1.0000 | 0.9008 | 0.9478 |
| Conflict | 1.0000 | 0.6400 | 0.7805 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.8017 |
| Deadline Near (+-1d) | 0.8182 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | 0.975 |
| False answer (GT empty) | 0.025 |
| False abstain (GT nonempty) | 0.1 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.6,0.8) | 1 | 1.0000 |
| [0.8,1.0) | 244 | 1.0000 |

ECE (vs bin midpoint): **0.1008** (n=245 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.7500 | 0.7500 | 0.6000 | 0.6000 | 0.6667 |
| conflict_deadline | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.8462 |
| doc_meeting_notes | 15 | 0.8571 | 0.8571 | 0.6875 | 0.6875 | 0.0000 |
| doc_simple | 20 | 0.9744 | 0.9744 | 0.9500 | 0.9500 | 0.0000 |
| edge_forwarded | 8 | 0.8571 | 0.8571 | 0.6250 | 0.6250 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 1.0000 | 0.7000 | 0.7000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 1.0000 | 0.7143 | 0.7143 | 0.0000 |
| edge_noisy_long | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_priority | 10 | 0.9474 | 0.9474 | 0.3000 | 0.6000 | 0.0000 |
| edge_special_format | 10 | 0.9474 | 0.9474 | 0.7000 | 0.7000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.9189 | 0.9189 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 0.9091 | 0.9091 | 0.6333 | 0.6667 | 0.0000 |
| missing_assignee | 10 | 0.9474 | 0.0000 | 0.9000 | 0.9000 | 0.0000 |
| missing_deadline | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8054**
- Edge case categories weighted Title F1: **0.7544**
- Delta: **-0.0510**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 35 | 14.0% |
| missed_task | 21 | 8.4% |
| complete_miss | 21 | 8.4% |
| missed_assignee | 20 | 8.0% |
| missed_conflict | 9 | 3.6% |
| deadline_off_by_one | 4 | 1.6% |
| hallucinated_task | 1 | 0.4% |
| false_positive_extraction | 1 | 0.4% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | false_positive_extraction | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|
| conflict_assignee | 4 | 0 | 0 | 0 | 4 | 5 | 4 | 4 |
| conflict_deadline | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 |
| doc_meeting_notes | 3 | 0 | 0 | 0 | 3 | 0 | 3 | 4 |
| doc_simple | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 1 |
| edge_forwarded | 2 | 0 | 0 | 0 | 2 | 0 | 2 | 3 |
| edge_mixed_lang | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| edge_nickname | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| edge_priority | 1 | 3 | 0 | 0 | 1 | 0 | 1 | 4 |
| edge_special_format | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 3 |
| edge_tricky_negative | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| email_ambiguous | 3 | 0 | 0 | 0 | 3 | 0 | 3 | 0 |
| email_simple | 5 | 1 | 0 | 0 | 5 | 0 | 5 | 10 |
| missing_assignee | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

## 6. Sample-Level Details (Errors Only)

### mx-189 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Đỗ | 2026-04-10 | pri=None
  - P: "update NDA contract asap" | Đỗ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-008 (email_simple, vi)

**Input:** Gửi Trần Thị Bình,

Phiền bạn chuẩn bị wireframe trang chủ trước ngày mai.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chuẩn bị wireframe trang chủ" | Trần Thị Bình | 2026-04-07 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-025 (email_simple, vi)

**Input:** @Nguyễn — chuẩn bị tài liệu thiết kế trước thứ Sáu này. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị tài liệu thiết kế" | Nguyễn | 2026-04-10 | pri=None
  - P: "chuẩn bị tài liệu thiết kế" | Nguyễn | None | pri=high

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "complete the API documentation" | Frankie | None | pri=None

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

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-126 (doc_meeting_notes, en)

**Input:** Meeting Notes — 2026-04-04

Attendees: Henry, Ivy

Action items:
- Henry: API documentation by Friday
- Ivy: homepage wireframe by Friday

**Expected tasks:** 2 | **Predicted:** 0
  - E: "API documentation" | Henry | 2026-04-10 | pri=None
  - E: "Homepage wireframe" | Ivy | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Test results" | Karen | 2026-04-03 | pri=None
  - P: "Submit test results" | Karen | 2026-04-03 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-003 (email_simple, vi)

**Input:** Gửi Bùi,

Phiền bạn chuẩn bị bản đánh giá nhân sự trước ngày 10 tháng 4.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chuẩn bị bản đánh giá nhân sự" | Bùi | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "hợp đồng NDA" | Trần Thị Bình | 2026-04-24 | pri=None
  - P: "báo cáo tháng 3" | Phạm Hương | 2026-04-24 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Prepare the design document" | Steve | 2026-04-03 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-013 (email_simple, vi)

**Input:** @Phạm Hương — dịch biên bản họp trước ngày 10 tháng 4. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Dịch biên bản họp" | Phạm Hương | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-009 (email_simple, vi)

**Input:** Chào team,

Nhờ Vũ Thảo review bảng số liệu tài chính trước tuần tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Review bảng số liệu tài chính" | Vũ Thảo | 2026-04-13 | pri=None
  - P: "review bảng số liệu tài chính" | Vũ Thảo | 2026-04-12 | pri=None

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-212 (edge_priority, vi)
Edge tags: explicit_priority

**Input:** [GẤP] Phạm ơi, review tài liệu API docs trước ngày mai. Rất gấp!

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Review tài liệu API docs" | Phạm | 2026-04-03 | pri=high

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chuẩn bị slide thuyết trình" | Vũ | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-244 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Lan ơi, tổng hợp proposal hợp tác trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tổng hợp proposal hợp tác" | Lan | 2026-04-03 | pri=None
  - P: "tổng hợp proposal hợp tác" | Lan | None | pri=None

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

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Cập nhật kết quả kiểm thử" | Lê | 2026-04-13 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-238 (edge_special_format, en)
Edge tags: special_format, markdown table

**Input:** | # | Assignee | Task | Due |
|---|----------|------|-----|
| 1 | Karen | Q1 report | 2026-04-03 |
| 2 | Leo | presentation slides | 2026-04-03 |

**Expected tasks:** 2 | **Predicted:** 0
  - E: "Q1 report" | Karen | 2026-04-03 | pri=None
  - E: "Presentation slides" | Leo | 2026-04-03 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

### eval-171 (missing_assignee, vi)

**Input:** Ai đó hoàn thành hợp đồng NDA trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Hoàn thành hợp đồng NDA" | None | 2026-04-03 | pri=None

**Errors:** missed_task, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-160 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Nguyễn Văn An phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Hoàng Nam phụ trách bản đánh giá nhân sự thay Nguyễn Văn An.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Bản đánh giá nhân sự" | Hoàng Nam | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-119 (doc_simple, vi)

**Input:** Kế hoạch dự án

Người phụ trách: Hồ Quang Huy
Nội dung: tài liệu API docs
Hạn nộp: 17/04/2026

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Tài liệu API docs" | Hồ Quang Huy | 2026-04-17 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "partnership proposal" | Henry | 2026-04-03 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### mx-183 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** Mọi người ơi, Hoàng Nam handle financial spreadsheet trước thứ Sáu tới. Let me know if any issues.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Handle financial spreadsheet" | Hoàng Nam | 2026-04-10 | pri=None
  - P: "handle financial spreadsheet" | Hoàng Nam | None | pri=None

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

### fw-208 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-05
Subject: Phân công

Nhờ Vũ chỉnh sửa hợp đồng NDA trước thứ Sáu.

---------- End forwarded ----------

FYI team, mọi...

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa hợp đồng NDA" | Vũ | 2026-04-10 | pri=None
  - P: "Chỉnh sửa hợp đồng NDA" | Vũ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-023 (email_simple, en)

**Input:** Grace — please finalize the project plan by next Friday.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Finalize project plan" | Grace | 2026-04-17 | pri=None
  - P: "finalize the project plan" | Grace | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-231 (edge_tricky_negative, vi)
Edge tags: tricky_negative, deferred

**Input:** Lưu ý: hợp đồng NDA chỉ cần làm khi phase 2 bắt đầu (chưa xác định).

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Làm hợp đồng NDA" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-206 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-03
Subject: Phân công

Nhờ Phan Đức Anh viết báo cáo Q1 trước thứ Sáu.

---------- End forwarded ----------

FYI team, ...

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Viết báo cáo Q1" | Phan Đức Anh | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-081 (email_ambiguous, en)

**Input:** Could Henry work on the partnership proposal sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Prepare partnership proposal" | Henry | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-236 (edge_special_format, en)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Tina] Q1 report (due: Friday)
* [Rachel] March report (due: Friday)
* [DONE] Deploy API endpoint

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Q1 report" | Tina | 2026-04-03 | pri=None
  - E: "March report" | Rachel | 2026-04-03 | pri=None
  - P: "Q1 report" | Tina | None | pri=None
  - P: "March report" | Rachel | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-091 (email_ambiguous, en)

**Input:** Could Diana work on the March report sometime soon?

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Submit March report" | Diana | None | pri=None

**Errors:** missed_task, missed_assignee, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-207 (edge_forwarded, vi)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-04-04
Subject: Phân công

Nhờ Đặng Tuấn Kiệt chuẩn bị wireframe trang chủ trước thứ Sáu.

---------- End forwarded -------...

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chuẩn bị wireframe trang chủ" | Đặng Tuấn Kiệt | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Submit the test results" | Olivia | 2026-04-08 | pri=None

**Errors:** missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}


## 7. Summary Statistics

- Fully correct samples: **202/250** (80.8%)
- Samples with errors: **48/250** (19.2%)