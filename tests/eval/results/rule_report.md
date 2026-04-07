# Evaluation Report: rule

Generated: 2026-04-03T19:46:34
Dataset: 250 samples, 17 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.5027 | 0.6801 | 0.5781 |
| Assignee | 0.7676 | 0.5420 | 0.6353 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.6281 |
| Deadline Near (+-1d) | 0.6405 |

## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 10 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| conflict_deadline | 15 | 0.4000 | 0.0000 | 0.0667 | 0.0667 | 0.0000 |
| doc_meeting_notes | 15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| doc_simple | 20 | 0.2963 | 0.0000 | 0.4000 | 0.4000 | 0.0000 |
| edge_forwarded | 8 | 0.8889 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_mixed_lang | 10 | 0.6000 | 0.3750 | 0.3000 | 0.3000 | 0.0000 |
| edge_nickname | 7 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_noisy_long | 10 | 0.3333 | 0.7000 | 1.0000 | 1.0000 | 0.0000 |
| edge_priority | 10 | 1.0000 | 0.9000 | 0.4000 | 0.7000 | 0.0000 |
| edge_special_format | 10 | 0.1000 | 0.1818 | 0.1000 | 0.1000 | 0.0000 |
| edge_tricky_negative | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 20 | 0.2000 | 0.2500 | 0.0000 | 0.0000 | 0.0000 |
| email_multi_task | 25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| email_no_task | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 30 | 0.6000 | 0.6250 | 0.3333 | 0.3333 | 0.0000 |
| missing_assignee | 10 | 0.7000 | 0.0000 | 0.7000 | 0.7000 | 0.0000 |
| missing_deadline | 10 | 0.7000 | 0.3529 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.4885**
- Edge case categories weighted Title F1: **0.4921**
- Delta: **+0.0036**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| hallucinated_task | 138 | 55.2% |
| missed_assignee | 112 | 44.8% |
| missed_task | 79 | 31.6% |
| wrong_deadline | 77 | 30.8% |
| wrong_assignee | 43 | 17.2% |
| false_positive_extraction | 40 | 16.0% |
| missed_conflict | 25 | 10.0% |
| deadline_off_by_one | 3 | 1.2% |

## 5. Per-Category Error Heatmap

| Category | deadline_off_by_one | false_positive_extraction | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_assignee | wrong_deadline |
|----------|---|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 0 | 10 | 10 | 10 | 10 | 0 | 10 |
| conflict_deadline | 0 | 0 | 9 | 15 | 15 | 9 | 6 | 14 |
| doc_simple | 0 | 0 | 19 | 20 | 0 | 12 | 8 | 12 |
| edge_forwarded | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| edge_mixed_lang | 0 | 0 | 4 | 7 | 0 | 4 | 3 | 7 |
| edge_nickname | 0 | 0 | 0 | 7 | 0 | 0 | 7 | 0 |
| edge_noisy_long | 0 | 0 | 10 | 3 | 0 | 0 | 3 | 0 |
| edge_priority | 3 | 0 | 0 | 1 | 0 | 0 | 1 | 3 |
| edge_special_format | 0 | 0 | 10 | 10 | 0 | 10 | 0 | 8 |
| edge_tricky_negative | 0 | 15 | 15 | 0 | 0 | 0 | 0 | 0 |
| email_ambiguous | 0 | 0 | 16 | 17 | 0 | 16 | 1 | 0 |
| email_no_task | 0 | 25 | 25 | 0 | 0 | 0 | 0 | 0 |
| email_simple | 0 | 0 | 12 | 15 | 0 | 12 | 3 | 20 |
| missing_assignee | 0 | 0 | 3 | 0 | 0 | 3 | 7 | 3 |
| missing_deadline | 0 | 0 | 3 | 7 | 0 | 3 | 4 | 0 |

## 6. Sample-Level Details (Errors Only)

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None
  - P: "@Nguyễn — hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-03 | pri=None

**Errors:** wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-117 (doc_simple, vi)

**Input:** Kế hoạch dự án

Người phụ trách: Ngô
Nội dung: báo cáo Q1
Hạn nộp: 06/04/2026

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Báo cáo Q1" | Ngô | 2026-04-06 | pri=None
  - P: "Kế hoạch dự án" | Kế | 2026-04-06 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-060 (email_no_task, vi)

**Input:** Cảm ơn mọi người đã tham gia buổi workshop hôm qua. Slide đã được upload.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Cảm ơn mọi người đã tham gia buổi workshop hôm qua. Slide đã được upload" | Cảm | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-070 (email_no_task, en)

**Input:** Test results this week look good. No critical issues found.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Test results this week look good. No critical issues found" | Test | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-056 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Just pushed code to feature/auth. Feel free to pull and test" | Just | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-073 (email_no_task, vi)

**Input:** Tôi đã hoàn thành xong phần thiết kế database rồi ạ.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Tôi đã hoàn thành xong phần thiết kế database rồi ạ" | Tôi | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-247 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Hương ơi, viết báo cáo Q1 trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết báo cáo Q1" | Hương | 2026-04-03 | pri=None
  - P: "Bạn Hương ơi, viết báo cáo Q1" | Bạn Hương | 2026-04-03 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-088 (email_ambiguous, vi)

**Input:** Bạn Phạm Hương thu xếp nộp bảng số liệu tài chính khi thuận tiện nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Nộp bảng số liệu tài chính" | Phạm Hương | None | pri=None
  - P: "Bạn Phạm Hương thu xếp nộp bảng số liệu tài chính khi thuận tiện nhé" | Bạn Phạm Hương | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-170 (missing_deadline, en)

**Input:** Reminder for Paul: please revise the Q1 report when you can.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Revise Q1 report" | Paul | None | pri=None
  - P: "revise the Q1 report when you can" | Reminder | None | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-026 (email_simple, vi)

**Input:** Hi Phạm,

Bạn chỉnh sửa slide thuyết trình trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa slide thuyết trình" | Phạm | 2026-04-12 | pri=None
  - P: "Hi Phạm" | Hi Phạm | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### ac-157 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Đỗ Văn Hải phụ trách wireframe trang chủ, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Lê Minh Đức phụ trách wireframe trang chủ thay Đỗ Văn Hải.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Wireframe trang chủ" | Lê Minh Đức | 2026-04-10 | pri=None
  - P: "Email thread" | Đỗ Văn Hải | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-106 (doc_simple, vi)

**Input:** PHÂN CÔNG CÔNG VIỆC

- Nhân viên: Phạm Hương
- Nhiệm vụ: bản kế hoạch dự án
- Deadline: 18/04/2026

**Expected tasks:** 1 | **Predicted:** 3
  - E: "Bản kế hoạch dự án" | Phạm Hương | 2026-04-18 | pri=None
  - P: "Nhân viên: Phạm Hương" | Nhân | 2026-04-18 | pri=None
  - P: "Nhiệm vụ: bản kế hoạch dự án" | Nhiệm | 2026-04-18 | pri=None
  - P: "Deadline: 18/04/2026" | Deadline | 2026-04-18 | pri=None

**Errors:** hallucinated_task, missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 2, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-240 (edge_special_format, en)
Edge tags: special_format, checklist with done item

**Input:** Sprint 14 checklist:

☐ financial spreadsheet — Charlie — by Friday
☐ test results — Quinn — by Friday
☑ Complete UI design (done)

**Expected tasks:** 2 | **Predicted:** 1
  - E: "Financial spreadsheet" | Charlie | 2026-04-10 | pri=None
  - E: "Test results" | Quinn | 2026-04-10 | pri=None
  - P: "Sprint 14 checklist" | Sprint | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-235 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ báo cáo tháng 3 — Lý Hoàng Long — trước thứ Sáu
☐ bảng số liệu tài chính — Hoàng Nam — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 1
  - E: "Báo cáo tháng 3" | Lý Hoàng Long | 2026-04-03 | pri=None
  - E: "Bảng số liệu tài chính" | Hoàng Nam | 2026-04-03 | pri=None
  - P: "Checklist sprint 14" | Checklist | 2026-04-03 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-109 (doc_simple, en)

**Input:** To-do list:

☐ design document — Karen — due 2026-04-21

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Design document" | Karen | 2026-04-21 | pri=None
  - P: "To-do list" | To | 2026-04-21 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-062 (email_no_task, en)

**Input:** Just pushed code to feature/auth. Feel free to pull and test.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Just pushed code to feature/auth. Feel free to pull and test" | Just | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-226 (edge_tricky_negative, vi)
Edge tags: tricky_negative, already-done report

**Input:** Báo cáo kết quả kiểm thử đã được gửi cho khách hàng vào sáng nay.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Báo cáo kết quả kiểm thử đã được gửi cho khách hàng vào sáng nay" | Báo | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-008 (email_simple, vi)

**Input:** Gửi Trần Thị Bình,

Phiền bạn chuẩn bị wireframe trang chủ trước ngày mai.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị wireframe trang chủ" | Trần Thị Bình | 2026-04-07 | pri=None
  - P: "Gửi Trần Thị Bình" | Gửi Trần Thị Bình | 2026-04-07 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-101 (doc_simple, vi)

**Input:** PHÂN CÔNG CÔNG VIỆC

- Nhân viên: Lê
- Nhiệm vụ: proposal hợp tác
- Deadline: 04/04/2026

**Expected tasks:** 1 | **Predicted:** 3
  - E: "Proposal hợp tác" | Lê | 2026-04-04 | pri=None
  - P: "Nhân viên: Lê" | Nhân | 2026-04-04 | pri=None
  - P: "Nhiệm vụ: proposal hợp tác" | Nhiệm | 2026-04-04 | pri=None
  - P: "Deadline: 04/04/2026" | Deadline | 2026-04-04 | pri=None

**Errors:** hallucinated_task, missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 2, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-242 (edge_special_format, en)
Edge tags: special_format, markdown table

**Input:** | # | Assignee | Task | Due |
|---|----------|------|-----|
| 1 | Steve | Q1 report | 2026-04-10 |
| 2 | Charlie | presentation slides | 2026-04-10 |

**Expected tasks:** 2 | **Predicted:** 1
  - E: "Q1 report" | Steve | 2026-04-10 | pri=None
  - E: "Presentation slides" | Charlie | 2026-04-10 | pri=None
  - P: "| # | Assignee | Task | Due |" | Assignee | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-246 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Mai ơi, soạn hợp đồng NDA trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Soạn hợp đồng NDA" | Mai | 2026-04-03 | pri=None
  - P: "Bạn Mai ơi, soạn hợp đồng NDA" | Bạn Mai | 2026-04-03 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### sf-241 (edge_special_format, vi)
Edge tags: special_format, checklist with done item

**Input:** Checklist sprint 14:

☐ bản kế hoạch dự án — Lê Minh Đức — trước thứ Sáu
☐ bản đánh giá nhân sự — Vũ Thảo — trước thứ Sáu
☑ Hoàn thành thiết kế UI (done)

**Expected tasks:** 2 | **Predicted:** 1
  - E: "Bản kế hoạch dự án" | Lê Minh Đức | 2026-04-10 | pri=None
  - E: "Bản đánh giá nhân sự" | Vũ Thảo | 2026-04-10 | pri=None
  - P: "Checklist sprint 14" | Checklist | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 2}, assignee={'tp': 0, 'fp': 0, 'fn': 2}, deadline={'exact': 0, 'near': 0, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-029 (email_simple, vi)

**Input:** Hi Phan Đức Anh,

Bạn hoàn thành bản kế hoạch dự án trong vòng 2 ngày giúp mình nhé. Thanks!

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản kế hoạch dự án" | Phan Đức Anh | 2026-04-01 | pri=None
  - P: "Hi Phan Đức Anh" | Hi Phan Đức Anh | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-180 (missing_assignee, vi)

**Input:** Ai đó hoàn thành báo cáo Q1 trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành báo cáo Q1" | None | 2026-04-10 | pri=None
  - P: "Ai đó hoàn thành báo cáo Q1" | Ai | 2026-04-10 | pri=None

**Errors:** wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-223 (edge_tricky_negative, vi)
Edge tags: tricky_negative, self-completion past

**Input:** Mình đã hoàn thành review tài liệu thiết kế hôm qua.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Mình đã hoàn thành review tài liệu thiết kế hôm qua" | Mình | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-097 (email_ambiguous, vi)

**Input:** Bạn Bùi Lan Anh thu xếp viết hợp đồng NDA khi thuận tiện nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Viết hợp đồng NDA" | Bùi Lan Anh | None | pri=None
  - P: "Bạn Bùi Lan Anh thu xếp viết hợp đồng NDA khi thuận tiện nhé" | Bạn Bùi Lan Anh | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### fw-203 (edge_forwarded, en)
Edge tags: forwarded, nested_email

**Input:** ---------- Forwarded message ----------
From: director@company.com
Date: 2026-03-31
Subject: Assignment

Please ask Eve to check the partnership proposal by Friday.

---------- End forwarded ---------...

**Expected tasks:** 1 | **Predicted:** 2
  - E: "Check partnership proposal" | Eve | 2026-04-03 | pri=None
  - P: "ask Eve to check the partnership proposal" | Eve | 2026-04-03 | pri=None
  - P: "take note" | Forwarded | 2026-03-31 | pri=None

**Errors:** hallucinated_task
**Scores:** title={'tp': 1, 'fp': 1, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None
  - P: "nộp" | Ngô Thanh Tùng | 2026-04-02 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### dc-141 (conflict_deadline, en)

**Input:** Email thread:

[Email 1 — 2026-04-02]
Bob, please submit the partnership proposal by Friday.

[Email 2 — 2026-04-04]
Update: the partnership proposal is now due by tomorrow.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Partnership proposal" | Bob | 2026-04-05 | pri=None
  - P: "submit the partnership proposal" | Friday | 2026-04-10 | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### nn-245 (edge_nickname, vi)
Edge tags: nickname, informal_name

**Input:** Bạn Thảo ơi, chỉnh sửa tài liệu thiết kế trước thứ Sáu.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chỉnh sửa tài liệu thiết kế" | Thảo | 2026-04-03 | pri=None
  - P: "Bạn Thảo ơi, chỉnh sửa tài liệu thiết kế" | Bạn Thảo | 2026-04-03 | pri=None

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
  - P: "Email thread" | Lê Minh Đức | 2026-04-03 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-064 (email_no_task, vi)

**Input:** Kết quả kiểm thử tuần này khả quan. Không có lỗi nghiêm trọng nào.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Kết quả kiểm thử tuần này khả quan. Không có lỗi nghiêm trọng nào" | Kết | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-249 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Frankie, complete the API documentation by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Complete API documentation" | Frankie | 2026-04-10 | pri=None
  - P: "Hey Frankie, complete the API documentation" | Hey Frankie | 2026-04-10 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### mx-185 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update Q1 report" | Hoàng | 2026-04-17 | pri=None
  - P: "@Hoàng: update Q1 report asap, deadline là" | Hoàng | 2026-04-03 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### nn-248 (edge_nickname, en)
Edge tags: nickname, informal_name

**Input:** Hey Di, submit the Q1 report by Friday pls.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit Q1 report" | Di | 2026-04-03 | pri=None
  - P: "Hey Di, submit the Q1 report" | Hey Di | 2026-04-03 | pri=None

**Errors:** missed_assignee, wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-225 (edge_tricky_negative, vi)
Edge tags: tricky_negative, email signature

**Input:** Nguyễn Văn An
Senior Developer
ĐT: 0912-345-678
Email: an@company.com

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Nguyễn Văn An" | Nguyễn Văn An | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-232 (edge_tricky_negative, en)
Edge tags: tricky_negative, attachment reference

**Input:** Attached: project plan.pdf (for reference)

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Attached: project plan.pdf (for reference)" | Attached | None | pri=None

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
  - P: "[Bob] project plan (due: Friday)" | Bob | 2026-04-10 | pri=None
  - P: "[Charlie] partnership proposal (due: Friday)" | Charlie | 2026-04-10 | pri=None
  - P: "[DONE] Deploy API endpoint" | Deploy | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 1, 'fp': 2, 'fn': 1}, assignee={'tp': 1, 'fp': 0, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 2}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-094 (email_ambiguous, en)

**Input:** Could Steve work on the API documentation sometime soon?

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Submit API documentation" | Steve | None | pri=None
  - P: "Could Steve work on the API documentation sometime soon?" | Could Steve | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### dc-143 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-04-04]
Nguyễn, hợp đồng NDA nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-06]
Cập nhật: hợp đồng NDA cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hợp đồng NDA" | Nguyễn | 2026-04-07 | pri=None
  - P: "nộp" | Nguyễn | 2026-04-07 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### ac-156 (conflict_assignee, vi)

**Input:** Email thread:

[Email 1]
Phan Đức Anh phụ trách báo cáo tháng 3, nộp trước thứ Sáu.

[Email 2]
Đã đổi: Phạm Hương phụ trách báo cáo tháng 3 thay Phan Đức Anh.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Báo cáo tháng 3" | Phạm Hương | 2026-04-10 | pri=None
  - P: "Email thread" | Phan Đức Anh | 2026-04-10 | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline, missed_conflict
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### mx-184 (edge_mixed_lang, mixed)
Edge tags: code_switching

**Input:** @Phan Đức Anh: update March report asap, deadline là trước 15/4.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Update March report" | Phan Đức Anh | 2026-04-15 | pri=None
  - P: "@Phan Đức Anh: update March report asap, deadline là" | Phan Đức Anh | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-089 (email_ambiguous, vi)

**Input:** Trần Thị Bình cố gắng xong báo cáo tháng 3 càng sớm càng tốt ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị báo cáo tháng 3" | Trần Thị Bình | None | pri=None
  - P: "Trần Thị Bình cố gắng xong báo cáo tháng 3 càng sớm càng tốt ạ" | Trần Thị Bình | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-022 (email_simple, vi)

**Input:** Anh/chị Bùi Lan Anh ơi, nhờ hoàn thành bản kế hoạch dự án trước ngày 10 tháng 4 ạ.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành bản kế hoạch dự án" | Bùi Lan Anh | 2026-04-10 | pri=None
  - P: "hoàn thành bản kế hoạch dự án" | Anh | None | pri=None

**Errors:** missed_assignee, wrong_assignee, wrong_deadline
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-069 (email_no_task, vi)

**Input:** FYI: lịch nghỉ lễ 30/4 - 1/5 đã được cập nhật trên hệ thống.

**Expected tasks:** 0 | **Predicted:** 1
  - P: "FYI: lịch nghỉ lễ 30/4 - 1/5 đã được cập nhật trên hệ thống" | None | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Test results" | Karen | 2026-04-03 | pri=None
  - P: "submit the test results" | Friday | 2026-04-03 | pri=None

**Errors:** missed_assignee, wrong_assignee, missed_conflict
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 1}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### eval-003 (email_simple, vi)

**Input:** Gửi Bùi,

Phiền bạn chuẩn bị bản đánh giá nhân sự trước ngày 10 tháng 4.

Trân trọng,
Quản lý dự án

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Chuẩn bị bản đánh giá nhân sự" | Bùi | 2026-04-10 | pri=None
  - P: "Gửi Bùi" | Gửi Bùi | None | pri=None

**Errors:** missed_task, hallucinated_task, missed_assignee, wrong_deadline
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### tn-229 (edge_tricky_negative, en)
Edge tags: tricky_negative, question

**Input:** Does anyone know when the API documentation is due?

**Expected tasks:** 0 | **Predicted:** 1
  - P: "Does anyone know when the API documentation is due?" | Does | None | pri=None

**Errors:** hallucinated_task, false_positive_extraction
**Scores:** title={'tp': 0, 'fp': 1, 'fn': 0}, assignee={'tp': 0, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 0, 'total': 0}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-179 (missing_assignee, vi)

**Input:** Ai đó hoàn thành hợp đồng NDA trước thứ Sáu nhé.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Hoàn thành hợp đồng NDA" | None | 2026-04-10 | pri=None
  - P: "Ai đó hoàn thành hợp đồng NDA" | Ai | 2026-04-10 | pri=None

**Errors:** wrong_assignee
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 0, 'fp': 1, 'fn': 0}, deadline={'exact': 1, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}


_...and 133 more error samples (see JSON for full details)._


## 7. Summary Statistics

- Fully correct samples: **67/250** (26.8%)
- Samples with errors: **183/250** (73.2%)