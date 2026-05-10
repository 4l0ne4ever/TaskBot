# Evaluation Report: pipeline

Generated: 2026-05-10T12:09:36
Dataset: 1 samples, 1 categories
Errors (runtime): 0

## 1. Overall Metrics

| Metric | Precision | Recall | F1 |
|--------|-----------|--------|----|
| Title | 1.0000 | 1.0000 | 1.0000 |
| Assignee | 1.0000 | 1.0000 | 1.0000 |
| Conflict | 0.0000 | 0.0000 | 0.0000 |

| Metric | Score |
|--------|-------|
| Deadline Exact Match | 1.0000 |
| Deadline Near (+-1d) | 1.0000 |

| Abstention | Rate |
|------------|------|
| Correct abstain (GT empty) | n/a |
| False answer (GT empty) | n/a |
| False abstain (GT nonempty) | 0.0 |

| Confidence bin | n | Title match acc. |
|----------------|---|------------------|
| [0.8,1.0) | 1 | 1.0000 |

ECE (vs bin midpoint): **0.1000** (n=1 paired w/ confidence)


## 2. Per-Category Breakdown

| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |
|----------|---------|----------|-------------|----------|---------|-------------|
| edge_noisy_long | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |

## 3. Edge Case Performance

- Core categories weighted Title F1: **0.0000**
- Edge case categories weighted Title F1: **1.0000**
- Delta: **+1.0000**

## 4. Error Analysis


## 5. Per-Category Error Heatmap


## 6. Sample-Level Details (Errors Only)


## 7. Summary Statistics

- Fully correct samples: **1/1** (100.0%)
- Samples with errors: **0/1** (0.0%)