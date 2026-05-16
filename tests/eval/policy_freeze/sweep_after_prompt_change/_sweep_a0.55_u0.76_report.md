# Evaluation Report: pipeline

Generated: 2026-05-12T12:27:04
Dataset: 3 samples, 2 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 1.0000 | 1.0000 | 1.0000 |
| Assignee | 1.0000 | 1.0000 | 1.0000 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 0.3333 |
| Deadline Near (+-1d) | 0.3333 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | n/a |
| False answer (GT empty) | n/a |
| False abstain (GT nonempty) | 0.0 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.8,1.0) | 3 | 1.0000 |

ECE (vs bin midpoint): **0.1000** (n=3 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| edge_mixed_lang | 1 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 2 | 1.0000 | 1.0000 | 0.5000 | 0.5000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **1.0000**
- Edge case categories weighted Title F1: **1.0000**
- Delta: **+0.0000**

## 4. Error Analysis

| Error Type | Count | % of Samples |
|------------|-------|--------------|
| wrong_deadline | 2 | 66.7% |

## 5. Per-Category Error Heatmap

| Category | wrong_deadline |
|----------|---|
| edge_mixed_lang | 1 |
| email_simple | 1 |

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


## 7. Summary Statistics

- Fully correct samples: **1/3** (33.3%)
- Samples with errors: **2/3** (66.7%)