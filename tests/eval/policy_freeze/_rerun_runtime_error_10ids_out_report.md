# Evaluation Report: pipeline

Generated: 2026-05-10T11:45:03
Dataset: 10 samples, 7 categories
Errors (runtime): 2 (other=1, rate_limit_other=1)

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.9000 | 0.8182 | 0.8571 |
| Assignee | 1.0000 | 0.7000 | 0.8235 |
| Conflict | 1.0000 | 0.5000 | 0.6667 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.6364 |
| Deadline Near (+-1d) | 0.7273 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | n/a |
| False answer (GT empty) | n/a |
| False abstain (GT nonempty) | 0.2 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.8,1.0) | 9 | 1.0000 |

ECE (vs bin midpoint): **0.1000** (n=9 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_assignee | 1 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| conflict_deadline | 3 | 0.6667 | 0.5000 | 0.6667 | 0.6667 | 0.5000 |
| doc_meeting_notes | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_mixed_lang | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| edge_noisy_long | 2 | 0.6667 | 0.6667 | 0.5000 | 0.5000 | 0.0000 |
| edge_priority | 1 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| missing_assignee | 1 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.8333**
- Edge case categories weighted Title F1: **0.8334**
- Delta: **+0.0000**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| missed_assignee | 3 | 30.0% |
| wrong_deadline | 3 | 30.0% |
| missed_task | 2 | 20.0% |
| missed_conflict | 2 | 20.0% |
| complete_miss | 2 | 20.0% |
| deadline_off_by_one | 1 | 10.0% |
| hallucinated_task | 1 | 10.0% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|
| conflict_assignee | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| conflict_deadline | 1 | 0 | 1 | 2 | 2 | 1 | 1 |
| edge_noisy_long | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| edge_priority | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

## 6. Sample-Level Details (Errors Only)

### dc-138 (conflict_deadline, vi)

**Input:** Email thread:

[Email 1 — 2026-03-30]
Ngô Thanh Tùng, tài liệu thiết kế nộp trước thứ Sáu nhé.

[Email 2 — 2026-04-01]
Cập nhật: tài liệu thiết kế cần nộp trước ngày mai.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Tài liệu thiết kế" | Ngô Thanh Tùng | 2026-04-02 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, missed_conflict, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 1}

### nl-195 (edge_noisy_long, vi)
Edge tags: noisy, long_text, signature

**Input:** Chào team,

Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:

- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái
- Chi phí marketing đã được tối ưu
- Nhóm R&D đang nghi...

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Soạn bản đánh giá nhân sự" | Huỳnh | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### pr-211 (edge_priority, en)
Edge tags: explicit_priority

**Input:** High priority: Steve, prepare the design document within 2 days.

**Expected tasks:** 1 | **Predicted:** 1
  - E: "Prepare design document" | Steve | 2026-04-04 | pri=high
  - P: "prepare the design document" | Steve | 2026-04-03 | pri=high

**Errors:** deadline_off_by_one
**Scores:** title={'tp': 1, 'fp': 0, 'fn': 0}, assignee={'tp': 1, 'fp': 0, 'fn': 0}, deadline={'exact': 0, 'near': 1, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

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


## 7. Summary Statistics

- Fully correct samples: **4/10** (40.0%)
- Samples with errors: **6/10** (60.0%)