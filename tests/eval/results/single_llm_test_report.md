# Evaluation Report: single

Generated: 2026-04-03T03:33:18
Dataset: 3 samples, 2 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 1.0000 | 0.3333 | 0.5000 |
| Assignee | 1.0000 | 0.3333 | 0.5000 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.0000 |
| Deadline Near (+-1d) | 0.3333 |

## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| edge_mixed_lang | 1 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| email_simple | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.0000**
- Edge case categories weighted Title F1: **1.0000**
- Delta: **+1.0000**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| missed_task | 2 | 66.7% |
| missed_assignee | 2 | 66.7% |
| wrong_deadline | 2 | 66.7% |
| complete_miss | 2 | 66.7% |
| deadline_off_by_one | 1 | 33.3% |

## 5. Per-Category Error Heatmap

| Category | complete_miss | deadline_off_by_one | missed_assignee | missed_task | wrong_deadline |
|----------|---|---|---|---|---|
| edge_mixed_lang | 0 | 1 | 0 | 0 | 0 |
| email_simple | 2 | 0 | 2 | 2 | 2 |

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

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Chuẩn bị bảng số liệu tài chính" | Hoàng Nam | 2026-04-02 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}

### eval-004 (email_simple, vi)

**Input:** @Nguyễn — hoàn thành bản đánh giá nhân sự trước thứ Sáu tới. Ưu tiên cái này nhé.

**Expected tasks:** 1 | **Predicted:** 0
  - E: "Hoàn thành bản đánh giá nhân sự" | Nguyễn | 2026-04-10 | pri=None

**Errors:** missed_task, missed_assignee, wrong_deadline, complete_miss
**Scores:** title={'tp': 0, 'fp': 0, 'fn': 1}, assignee={'tp': 0, 'fp': 0, 'fn': 1}, deadline={'exact': 0, 'near': 0, 'total': 1}, conflict={'tp': 0, 'fp': 0, 'fn': 0}


## 7. Summary Statistics

- Fully correct samples: **0/3** (0.0%)
- Samples with errors: **3/3** (100.0%)