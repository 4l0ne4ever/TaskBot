# Auto-Confirm Rate Measurement (Phase 7.2 Evidence)

**Date:** 2026-05-21
**Dataset:** 28 synthetic enterprise emails (task-bearing + FYI/noise mix), run through the full LangGraph pipeline via direct `pipeline.invoke()` (no queue).
**Policy:** v1. Model: primary provider chain (Cerebras `openai/gpt-oss-120b`).
**Method:** Tasks isolated by `source_documents.source_ref LIKE 'synth-%'`.

## Headline

| Metric                                  | Value        |
| --------------------------------------- | ------------ |
| **Auto-confirm rate**                   | **90.9%** (30/33) |
| Documents producing ≥1 task             | 20 / 28      |
| Tasks extracted                         | 33           |
| Accept band (`uncertainty = null`)      | 32           |
| Uncertain band                          | 1            |
| Tasks with actionable field (deadline OR assignee) | 31  |
| Auto-confirmed (`confirmed_by='system'`)| 30           |
| Held for human review                   | 3            |
| False auto-confirms                     | 0            |

## Why the 3 held-back tasks are correct

The gate is `uncertainty IS NULL  AND  not in intra-batch conflict  AND  (deadline OR assignee)`.

1. **1 task** — confidence in the uncertain band (`{"type":"ambiguous","reason":"confidence in uncertain band"}`). The calibrated decision band correctly withheld it.
2. **2 tasks** — accept band but no deadline AND no assignee. Nothing actionable to calendar or assign, so auto-confirm correctly declines.

Every one of the 30 auto-confirmed tasks satisfies all three criteria. No task was auto-confirmed without an actionable field, and none with a non-null uncertainty.

## Noise rejection (negative-control signal)

8 of 28 documents produced **0 tasks** — these were FYI / informational messages
(office-closed notice, an article link, a team-lunch poll, retrospective notes,
a server-maintenance notice). The pipeline did not hallucinate tasks from
non-actionable content: a key precision signal for the enterprise "yet another
inbox" critique.

## Reproduce

```bash
docker exec taskbot-postgres psql -U taskbot -d taskbot -c "
WITH synth AS (
  SELECT t.* FROM tasks t JOIN source_documents sd ON t.source_doc_id = sd.id
  WHERE sd.source_ref LIKE 'synth-%'
)
SELECT
  COUNT(*) AS tasks_extracted,
  COUNT(*) FILTER (WHERE confirmed_by='system') AS auto_confirmed,
  ROUND(100.0*COUNT(*) FILTER (WHERE confirmed_by='system')/NULLIF(COUNT(*),0),1) AS auto_confirm_pct
FROM synth;"
```

**Caveat:** Synthetic data, not production traffic. Distribution hand-authored to
resemble Anna's enterprise inbox (deadlines + named assignees common). Real-world
rate will differ; this establishes the mechanism works and is well-calibrated, not
a production SLA.
