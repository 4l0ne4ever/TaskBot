# Evaluation Comparison Report

Generated: 2026-04-03T22:03:48
Methods: rule, single_llm_70b, single_llm, pipeline

## Overall Metrics

| Metric | rule | single_llm_70b | single_llm | pipeline |
|--------|-------|-------|-------|-------|
| Title F1 | 0.5781 | 0.8774 | 0.8931 | 0.8413 |
| Title Precision | 0.5027 | 0.8274 | 0.8409 | 0.7402 |
| Title Recall | 0.6801 | 0.9338 | 0.9522 | 0.9743 |
| Assignee F1 | 0.6353 | 0.9008 | 0.8880 | 0.7957 |
| Deadline Exact | 0.6281 | 0.5620 | 0.4793 | 0.1198 |
| Deadline Near | 0.6405 | 0.7190 | 0.6322 | 0.1446 |
| Conflict F1 | 0.0000 | 0.9434 | 0.9600 | 0.0000 |

## Per-Category Title F1

| Category | rule | single_llm_70b | single_llm | pipeline |
|----------|-------|-------|-------|-------|
| conflict_assignee | 0.0000 | 0.5926 | 0.5517 | 0.6897 |
| conflict_deadline | 0.4000 | 0.6667 | 0.6222 | 0.6222 |
| doc_meeting_notes | 1.0000 | 0.9688 | 0.9688 | 0.9688 |
| doc_simple | 0.2963 | 1.0000 | 1.0000 | 1.0000 |
| edge_forwarded | 0.8889 | 0.8750 | 1.0000 | 1.0000 |
| edge_mixed_lang | 0.6000 | 1.0000 | 1.0000 | 1.0000 |
| edge_nickname | 1.0000 | 0.8571 | 1.0000 | 1.0000 |
| edge_noisy_long | 0.3333 | 0.6897 | 0.6667 | 0.6667 |
| edge_priority | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| edge_special_format | 0.1000 | 0.9091 | 0.8889 | 0.8696 |
| edge_tricky_negative | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_ambiguous | 0.2000 | 0.8205 | 0.8421 | 0.8000 |
| email_multi_task | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| email_no_task | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| email_simple | 0.6000 | 0.8667 | 0.9831 | 0.9831 |
| missing_assignee | 0.7000 | 1.0000 | 1.0000 | 1.0000 |
| missing_deadline | 0.7000 | 0.7500 | 0.7500 | 0.9524 |

## Error Type Comparison

| Error Type | rule | single_llm_70b | single_llm | pipeline |
|------------|-------|-------|-------|-------|
| complete_miss | 0 | 5 | 7 | 1 |
| deadline_off_by_one | 3 | 28 | 28 | 5 |
| false_conflict | 0 | 3 | 1 | 0 |
| false_positive_extraction | 40 | 8 | 4 | 40 |
| hallucinated_task | 138 | 50 | 46 | 86 |
| missed_assignee | 112 | 35 | 36 | 77 |
| missed_conflict | 25 | 0 | 1 | 25 |
| missed_task | 79 | 18 | 13 | 7 |
| wrong_assignee | 43 | 15 | 21 | 18 |
| wrong_deadline | 77 | 58 | 73 | 150 |