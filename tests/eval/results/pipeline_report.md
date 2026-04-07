# Evaluation Report: pipeline

Generated: 2026-04-03T21:04:34
Dataset: 250 samples, 17 categories
Errors (runtime): 1

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.7402 | 0.9743 | 0.8413 |
| Assignee | 0.9113 | 0.7061 | 0.7957 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.1198 |
| Deadline Near (+-1d) | 0.1446 |

## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.6897 | 0.7000 | 0.0000 | 0.0000 | 0.0000 |
| conflict_deadline | 15 | 0.6222 | 0.8000 | 0.0000 | 0.0000 | 0.0000 |
| doc_meeting_notes | 15 | 0.9688 | 0.9153 | 0.0000 | 0.0625 | 0.0000 |
| doc_simple | 20 | 1.0000 | 0.9500 | 0.8500 | 0.8500 | 0.0000 |
| edge_forwarded | 8 | 1.0000 | 0.8571 | 0.0000 | 0.0000 | 0.0000 |
| edge_mixed_lang | 10 | 1.0000 | 0.4615 | 0.0000 | 0.0000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 0.1538 | 0.0000 | 0.0000 | 0.0000 |
| edge_noisy_long | 10 | 0.6667 | 0.6250 | 0.0000 | 0.0000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 0.8235 | 0.0000 | 0.1000 | 0.0000 |
| edge_special_format | 10 | 0.8696 | 0.9189 | 0.2000 | 0.3000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.8000 | 0.6000 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 0.8889 | 0.1000 | 0.1167 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 0.9831 | 0.8077 | 0.0667 | 0.0667 | 0.0000 |
| missing_assignee | 10 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| missing_deadline | 10 | 0.9524 | 0.5882 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.7821**
- Edge case categories weighted Title F1: **0.7195**
- Delta: **-0.0626**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 150 | 60.0% |
| hallucinated_task | 86 | 34.4% |
| missed_assignee | 77 | 30.8% |
| false_positive_extraction | 40 | 16.0% |
| missed_conflict | 25 | 10.0% |
| wrong_assignee | 18 | 7.2% |
| missed_task | 7 | 2.8% |
| deadline_off_by_one | 5 | 2.0% |
| complete_miss | 1 | 0.4% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | false_positive_extraction | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_assignee | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 0 | 0 | 9 | 3 | 10 | 0 | 3 | 10 |
| conflict_deadline | 0 | 0 | 0 | 15 | 5 | 15 | 1 | 0 | 15 |
| doc_meeting_notes | 0 | 1 | 0 | 1 | 5 | 0 | 1 | 0 | 14 |
| doc_simple | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 3 |
| edge_forwarded | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 8 |
| edge_mixed_lang | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 10 |
| edge_nickname | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 5 | 7 |
| edge_noisy_long | 0 | 0 | 0 | 10 | 5 | 0 | 0 | 1 | 10 |
| edge_priority | 0 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 9 |
| edge_special_format | 0 | 2 | 0 | 6 | 3 | 0 | 0 | 0 | 6 |
| edge_tricky_negative | 0 | 0 | 15 | 15 | 0 | 0 | 0 | 0 | 0 |
| email_ambiguous | 0 | 0 | 0 | 4 | 11 | 0 | 4 | 1 | 0 |
| email_multi_task | 0 | 1 | 0 | 0 | 12 | 0 | 0 | 0 | 20 |
| email_no_task | 0 | 0 | 25 | 25 | 0 | 0 | 0 | 0 | 0 |
| email_simple | 1 | 0 | 0 | 0 | 9 | 0 | 1 | 1 | 28 |
| missing_assignee | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 10 |
| missing_deadline | 0 | 0 | 0 | 1 | 5 | 0 | 0 | 2 | 0 |

## 6. Sample-Level Details (Errors Only)

### mx-189 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update NDA contract" | Đỗ | 2026-04-10 | pri=None
  - P: "update NDA contract" | None | None | pri=high

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-001 (email_simple, vi)

**Input:** Chào team,

Nhờ Hoàng Nam chuẩn bị bảng số liệu tài chính trong 3 ngày tới nhé. Cảm ơn.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | 2026-04-02 | pri=None
  - P: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None
  - P: "hoàn thành bản đánh giá nhân sự trước thứ Sáu tới" | Nguyễn | None | pri=None

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
  - P: "báo cáo tháng 3 trước thứ Sáu" | Đặng Tuấn Kiệt | None | pri=None
  - P: "proposal hợp tác trước thứ Sáu" | Dương Thị Mai | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-123 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-01

Tham dự: Phạm Hương, Lê Minh Đức

Action items:
- Phạm Hương: biên bản họp trước thứ Sáu
- Lê Minh Đức: tài liệu thiết kế trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Biên bản họp" | Phạm Hương | 2026-04-03 | pri=None
  - E: "Tài liệu thiết kế" | Lê Minh Đức | 2026-04-03 | pri=None
  - P: "biên bản họp trước thứ Sáu" | Phạm Hương | None | pri=None
  - P: "tài liệu thiết kế trước thứ Sáu" | Lê Minh Đức | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-002 (email_simple, en)

**Input:** Hi team,

Please ask Charlie to compile the test results by this Friday. Thanks.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Compile test results" | Charlie | 2026-04-03 | pri=None
  - P: "Compile test results" | Charlie | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-060 (email_no_task, vi)

**Input:** Cảm ơn mọi người đã tham gia buổi workshop hôm qua. Slide đã được upload.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Upload slide" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-042 (email_multi_task, en)
Edge tags: 3_tasks

**Input:** Hi all,

1. Tina: complete the Q1 report within 5 days.
2. Eve: complete the presentation slides within 7 days.
3. Henry: check the performance review within 3 days.

Thanks everyone.

**Expected tasks:** 3 | **Predicted:** 3
  - E: "Complete Q1 report" | Tina | 2026-04-15 | pri=None
  - E: "Complete presentation slides" | Eve | 2026-04-17 | pri=None
  - E: "Check performance review" | Henry | 2026-04-13 | pri=None
  - P: "complete the Q1 report within 5 days" | Tina | None | pri=None
  - P: "complete the presentation slides within 7 days" | Eve | None | pri=None
  - P: "check the performance review within 3 days" | Henry | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 3, 'fp': 0, 'fn': 0}, assignee={'tp': 3, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-070 (email_no_task, en)

**Input:** Test results this week look good. No critical issues found.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "No critical issues found" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-052 (email_multi_task, en)

**Input:** Hi all,

1. Jack: prepare the Q1 report within 3 days.
2. Henry: complete the homepage wireframe within 7 days.

Thanks everyone.

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Prepare Q1 report" | Jack | 2026-04-09 | pri=None
  - E: "Complete homepage wireframe" | Henry | 2026-04-13 | pri=None
  - P: "prepare the Q1 report" | Jack | None | pri=None
  - P: "complete the homepage wireframe" | Henry | 2026-04-09 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-056 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Pull and test feature/auth" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-073 (email_no_task, vi)

**Input:** Tôi đã hoàn thành xong phần thiết kế database rồi ạ.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Hoàn thành thiết kế database" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-247 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Hương ơi, viết báo cáo Q1 trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết báo cáo Q1" | Hương | 2026-04-03 | pri=None
  - P: "viết báo cáo Q1 trước thứ Sáu" | Bạn Hương | None | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-036 (email_multi_task, vi)
Edge tags: 3_tasks

**Input:** Chào team,

1. Hồ Quang Huy: chỉnh sửa bản kế hoạch dự án trong 2 ngày.
2. Trần Thị Bình: chuẩn bị slide thuyết trình trong 3 ngày.
3. Huỳnh Minh Tâm: chỉnh sửa file mockup UI trong 5 ngày.

Cảm ơn mọ...

**Expected tasks:** 3 | **Predicted:** 3
  - E: "Chỉnh sửa bản kế hoạch dự án" | Hồ Quang Huy | 2026-04-06 | pri=None
  - E: "Chuẩn bị slide thuyết trình" | Trần Thị Bình | 2026-04-07 | pri=None
  - E: "Chỉnh sửa file mockup UI" | Huỳnh Minh Tâm | 2026-04-09 | pri=None
  - P: "chỉnh sửa bản kế hoạch dự án" | None | None | pri=None
  - P: "chuẩn bị slide thuyết trình" | Trần Thị Bình | None | pri=None
  - P: "chỉnh sửa file mockup UI" | Huỳnh Minh Tâm | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 3, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-170 (missing_deadline, en)

**Input:** Reminder for Paul: please revise the Q1 report when you can.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Revise Q1 report" | Paul | None | pri=None
  - P: "Revise Q1 report" | None | None | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-128 (doc_meeting_notes, vi)

**Input:** Biên bản họp ngày 2026-04-06

Tham dự: Huỳnh Minh Tâm, Lê Minh Đức

Action items:
- Huỳnh Minh Tâm: tài liệu thiết kế trước thứ Sáu
- Lê Minh Đức: báo cáo Q1 trước thứ Sáu

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Huỳnh Minh Tâm | 2026-04-10 | pri=None
  - E: "Báo cáo Q1" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "tài liệu thiết kế trước thứ Sáu" | Huỳnh Minh Tâm | None | pri=None
  - P: "báo cáo Q1 trước thứ Sáu" | Lê Minh Đức | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 1}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-026 (email_simple, vi)

**Input:** Hi Phạm,

Bạn chỉnh sửa slide thuyết trình trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa slide thuyết trình" | Phạm | 2026-04-12 | pri=None
  - P: "Chỉnh sửa slide thuyết trình" | Phạm | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-031 (email_multi_task, vi)
Edge tags: 3_tasks

**Input:** Chào team,

1. Đặng Tuấn Kiệt: nộp báo cáo Q1 trong 7 ngày.
2. Phạm Hương: hoàn thành kết quả kiểm thử trong 5 ngày.
3. Phan Đức Anh: kiểm tra bản kế hoạch dự án trong 7 ngày.

Cảm ơn mọi người.

**Expected tasks:** 3 | **Predicted:** 3
  - E: "Nộp báo cáo Q1" | Đặng Tuấn Kiệt | 2026-04-06 | pri=None
  - E: "Hoàn thành kết quả kiểm thử" | Phạm Hương | 2026-04-04 | pri=None
  - E: "Kiểm tra bản kế hoạch dự án" | Phan Đức Anh | 2026-04-06 | pri=None
  - P: "nộp báo cáo Q1" | None | None | pri=None
  - P: "hoàn thành kết quả kiểm thử" | Phạm Hương | None | pri=None
  - P: "kiểm tra bản kế hoạch dự án" | Phan Đức Anh | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 3, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 3}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-157 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Wireframe trang chủ" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "nộp trước thứ Sáu" | Đỗ Văn Hải | None | pri=None
  - P: "phụ trách wireframe trang chủ" | Lê Minh Đức | None | pri=None

**Errors:** hallucinated_task, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-106 (doc_simple, vi)

**Input:** PHÂN CÔNG CÔNG VIỆC

- Nhân viên: Phạm Hương
- Nhiệm vụ: bản kế hoạch dự án
- Deadline: 18/04/2026

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Bản kế hoạch dự án" | Phạm Hương | 2026-04-18 | pri=None
  - P: "bản kế hoạch dự án" | Phạm Hương | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-240 (edge_special_format, en)
Edge tags: special_format, checklist with done item

**Input:** Sprint 14 checklist:

☐ financial spreadsheet — Charlie — by Friday
☐ test results — Quinn — by Friday
☑ Complete UI design (done)

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Financial spreadsheet" | Charlie | 2026-04-10 | pri=None
  - E: "Test results" | Quinn | 2026-04-10 | pri=None
  - P: "financial spreadsheet" | Charlie | None | pri=None
  - P: "test results" | Quinn | 2026-04-09 | pri=None
  - P: "Complete UI design" | None | None | pri=None

**Errors:** hallucinated_task, deadline_off_by_one
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-235 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ báo cáo tháng 3 — Lý Hoàng Long — trước thứ Sáu
☐ bảng số liệu tài chính — Hoàng Nam — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Báo cáo tháng 3" | Lý Hoàng Long | 2026-04-03 | pri=None
  - E: "Bảng số liệu tài chính" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "báo cáo tháng 3" | Lý Hoàng Long | None | pri=None
  - P: "bảng số liệu tài chính" | Hoàng Nam | None | pri=None
  - P: "Hoàn thành thiết kế UI" | None | None | pri=None

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-041 (email_multi_task, vi)

**Input:** Chào team,

1. Đỗ Văn Hải: chuẩn bị bảng số liệu tài chính trong 2 ngày.
2. Vũ Thảo: soạn hợp đồng NDA trong 5 ngày.

Cảm ơn mọi người.

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Chuẩn bị bảng số liệu tài chính" | Đỗ Văn Hải | 2026-04-11 | pri=None
  - E: "Soạn hợp đồng NDA" | Vũ Thảo | 2026-04-14 | pri=None
  - P: "chuẩn bị bảng số liệu tài chính" | None | None | pri=None
  - P: "soạn hợp đồng NDA" | Vũ Thảo | 2026-04-15 | pri=None

**Errors:** missed_assignee, deadline_off_by_one
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 1, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-062 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Pull and test feature/auth" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-226 (edge_tricky_negative, vi)
Edge tags: tricky_negative, already-done report

**Input:** Báo cáo kết quả kiểm thử đã được gửi cho khách hàng vào sáng nay.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Báo cáo kết quả kiểm thử" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-008 (email_simple, vi)

**Input:** Gửi Trần Thị Bình,

Phiền bạn chuẩn bị wireframe trang chủ trước ngày mai.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị wireframe trang chủ" | Trần Thị Bình | 2026-04-07 | pri=None
  - P: "Chuẩn bị wireframe trang chủ" | Trần Thị Bình | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Kiểm tra hợp đồng NDA trước thứ Sáu" | Đỗ | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-246 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Mai ơi, soạn hợp đồng NDA trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Soạn hợp đồng NDA" | Mai | 2026-04-03 | pri=None
  - P: "soạn hợp đồng NDA trước thứ Sáu" | Bạn Mai | None | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-241 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ bản kế hoạch dự án — Lê Minh Đức — trước thứ Sáu
☐ bản đánh giá nhân sự — Vũ Thảo — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Bản kế hoạch dự án" | Lê Minh Đức | 2026-04-10 | pri=None
  - E: "Bản đánh giá nhân sự" | Vũ Thảo | 2026-04-10 | pri=None
  - P: "bản kế hoạch dự án" | None | None | pri=None
  - P: "bản đánh giá nhân sự" | Vũ Thảo | None | pri=None
  - P: "Hoàn thành thiết kế UI" | None | None | pri=None

**Errors:** hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-029 (email_simple, vi)

**Input:** Hi Phan Đức Anh,

Bạn hoàn thành bản kế hoạch dự án trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản kế hoạch dự án" | Phan Đức Anh | 2026-04-01 | pri=None
  - P: "hoàn thành bản kế hoạch dự án" | None | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-180 (missing_assignee, vi)

**Input:** Ai đó hoàn thành báo cáo Q1 trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo Q1" | None | 2026-04-10 | pri=None
  - P: "hoàn thành báo cáo Q1 trước thứ Sáu" | Ai đó | None | pri=None

**Errors:** wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-223 (edge_tricky_negative, vi)
Edge tags: tricky_negative, self-completion past

**Input:** Mình đã hoàn thành review tài liệu thiết kế hôm qua.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "review tài liệu thiết kế" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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
  - P: "Check partnership proposal" | Eve | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-025 (email_simple, vi)

**Input:** @Nguyễn — chuẩn bị tài liệu thiết kế trước thứ Sáu này. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị tài liệu thiết kế" | Nguyễn | 2026-04-10 | pri=None
  - P: "chùn biãn tài liệu thiết kế" | None | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "nộp tài liệu thiết kế trước thứ Sáu" | Ngô Thanh Tùng | None | pri=None
  - P: "nộp tài liệu thiết kế trước ngày mai" | None | 2026-04-02 | pri=None

**Errors:** hallucinated_task, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-054 (email_multi_task, vi)

**Input:** Chào team,

1. Đỗ Văn Hải: gửi bảng số liệu tài chính trong 7 ngày.
2. Lý Hoàng Long: kiểm tra slide thuyết trình trong 2 ngày.

Cảm ơn mọi người.

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Gửi bảng số liệu tài chính" | Đỗ Văn Hải | 2026-04-15 | pri=None
  - E: "Kiểm tra slide thuyết trình" | Lý Hoàng Long | 2026-04-10 | pri=None
  - P: "gửi bảng số liệu tài chính" | None | None | pri=None
  - P: "kiểm tra slide thuyết trình" | Lý Hoàng Long | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-141 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-02]
Bob, please submit the partnership proposal by Friday.

[Email 2 — 2026-04-04]
Update: the partnership proposal is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Partnership proposal" | Bob | 2026-04-05 | pri=None
  - P: "Submit partnership proposal" | None | None | pri=None
  - P: "Update partnership proposal deadline" | None | 2026-04-05 | pri=None

**Errors:** hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### nn-245 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Thảo ơi, chỉnh sửa tài liệu thiết kế trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Thảo | 2026-04-03 | pri=None
  - P: "chỉnh sửa tài liệu thiết kế trước thứ Sáu" | Bạn Thảo | None | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-153 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Lê Minh Đức phụ trách bản đánh giá nhân sự, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Đặng Tuấn Kiệt phụ trách bản đánh giá nhân sự thay Lê Minh Đức.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Bản đánh giá nhân sự" | Đặng Tuấn Kiệt | 2026-04-03 | pri=None
  - P: "nộp bản đánh giá nhân sự trước thứ Sáu" | Lê Minh Đức | None | pri=None
  - P: "phụ trách bản đánh giá nhân sự" | Đông Tuấn Kiệt | None | pri=None

**Errors:** hallucinated_task, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-064 (email_no_task, vi)

**Input:** Kết quả kiểm thử tuần này khả quan. Không có lỗi nghiêm trọng nào.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Kiểm thử tuần này" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "complete the API documentation" | Frankie | None | pri=low

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-035 (email_multi_task, en)

**Input:** Hi all,

1. Ivy: complete the NDA contract within 7 days.
2. Maria: draft the project plan within 5 days.

Thanks everyone.

**Expected tasks:** 2 | **Predicted:** 2
  - E: "Complete NDA contract" | Ivy | 2026-04-10 | pri=None
  - E: "Draft project plan" | Maria | 2026-04-08 | pri=None
  - P: "complete the NDA contract within 7 days" | Ivy | None | pri=None
  - P: "draft the project plan within 5 days" | Maria | None | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 2, 'fp': 0, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "update Q1 report" | None | None | pri=high

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-248 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Di, submit the Q1 report by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit Q1 report" | Di | 2026-04-03 | pri=None
  - P: "Submit Q1 report" | None | None | pri=None

**Errors:** missed_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-225 (edge_tricky_negative, vi)
Edge tags: tricky_negative, email signature

**Input:** Nguyễn Văn An
Senior Developer
ĐT: 0912-345-678
Email: an@company.com

**Expected tasks:** 0 | **Predicted:** 4
  - P: "Meeting on 2026-04-06" | None | 2026-04-06 | pri=None
  - P: "Review code changes" | Nguyễn Văn An | None | pri=None
  - P: "Fix bug in feature X" | Nguyễn Văn An | None | pri=high
  - P: "Discuss project timeline" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 4, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-232 (edge_tricky_negative, en)
Edge tags: tricky_negative, attachment reference

**Input:** Attached: project plan.pdf (for reference)

**Expected tasks:** 0 | **Predicted:** 1
  - P: "project plan.pdf (for reference)" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-243 (edge_special_format, en)
Edge tags: special_format, custom bracket format

**Input:** TODO:
* [Bob] project plan (due: Friday)
* [Charlie] partnership proposal (due: Friday)
* [DONE] Deploy API endpoint

**Expected tasks:** 2 | **Predicted:** 3
  - E: "Project plan" | Bob | 2026-04-10 | pri=None
  - E: "Partnership proposal" | Charlie | 2026-04-10 | pri=None
  - P: "project plan" | Bob | None | pri=None
  - P: "partnership proposal" | Charlie | 2026-04-08 | pri=None
  - P: "Deploy API endpoint" | None | None | pri=None

**Errors:** hallucinated_task, wrong_deadline
**Scores:** title={'tp': 2, 'fp': 1, 'fn': 0}, assignee={'tp': 2, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-094 (email_ambiguous, en)

**Input:** Could Steve work on the API documentation sometime soon?

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit API documentation" | Steve | None | pri=None
  - P: "Work on API documentation" | None | None | pri=None

**Errors:** missed_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-143 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-04]
Nguyễn, hợp đồng NDA nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-06]
Cập nhật: hợp đồng NDA cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Hợp đồng NDA" | Nguyễn | 2026-04-07 | pri=None
  - P: "Nộp hợp đồng NDA trước thứ Sáu" | Nguyễn | None | pri=None
  - P: "Nộp hợp đồng NDA trước ngày mai" | Nguyễn | 2026-04-07 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 2, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None
  - P: "Báo cáo tháng 3" | Phan Đức Anh | None | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}


_...and 167 more error samples (see JSON for full details)._


## 7. Summary Statistics

- Fully correct samples: **33/250** (13.2%)
- Samples with errors: **217/250** (86.8%)