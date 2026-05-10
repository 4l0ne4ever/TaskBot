# Evaluation Report: pipeline

Generated: 2026-05-10T11:50:52
Dataset: 2 samples, 2 categories
Errors (runtime): 1 (daily_quota=1)

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 0.5000 | 0.5000 | 0.5000 |
| Assignee | 1.0000 | 0.5000 | 0.6667 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.0000 |
| Deadline Near (+-1d) | 0.5000 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | n/a |
| False answer (GT empty) | n/a |
| False abstain (GT nonempty) | 0.5 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.6,0.8) | 1 | 1.0000 |

ECE (vs bin midpoint): **0.3000** (n=1 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| conflict_deadline | 1 | 0.6667 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| edge_noisy_long | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.6667**
- Edge case categories weighted Title F1: **0.0000**
- Delta: **-0.6667**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| hallucinated_task | 1 | 50.0% |
| deadline_off_by_one | 1 | 50.0% |
| missed_conflict | 1 | 50.0% |
| missed_task | 1 | 50.0% |
| missed_assignee | 1 | 50.0% |
| wrong_deadline | 1 | 50.0% |
| complete_miss | 1 | 50.0% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | hallucinated_task | missed_assignee | missed_conflict | missed_task | wrong_deadline |
|----------|---|---|---|---|---|---|---|
| conflict_deadline | 0 | 1 | 1 | 0 | 1 | 0 | 0 |
| edge_noisy_long | 1 | 0 | 0 | 1 | 0 | 1 | 1 |

## 6. Sample-Level Details (Errors Only)

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


## 7. Summary Statistics

- Fully correct samples: **0/2** (0.0%)
- Samples with errors: **2/2** (100.0%)