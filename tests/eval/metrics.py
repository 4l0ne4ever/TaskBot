"""
Evaluation metrics for TaskBot extraction quality.

Compares predicted extraction results against labeled ground truth.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from datetime import date, timedelta


TITLE_MATCH_THRESHOLD = 0.6


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _title_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v[:10])
    except (ValueError, TypeError):
        return None


def _match_tasks(expected: list[dict], predicted: list[dict]) -> list[tuple[dict, dict | None]]:
    """Greedy best-match pairing by title similarity."""
    used = set()
    pairs: list[tuple[dict, dict | None]] = []
    for exp in expected:
        best_idx = -1
        best_score = -1.0
        for j, pred in enumerate(predicted):
            if j in used:
                continue
            score = _title_sim(exp.get("title", ""), pred.get("title", ""))
            if score > best_score:
                best_score = score
                best_idx = j
        if best_idx >= 0 and best_score >= TITLE_MATCH_THRESHOLD:
            pairs.append((exp, predicted[best_idx]))
            used.add(best_idx)
        else:
            pairs.append((exp, None))
    return pairs


def _f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def evaluate_sample(expected: dict, predicted: dict) -> dict:
    """Evaluate one sample. Both dicts have 'tasks', 'conflicts', 'missing_fields'."""
    exp_tasks = expected.get("tasks") or []
    pred_tasks = predicted.get("tasks") or []

    pairs = _match_tasks(exp_tasks, pred_tasks)
    unmatched_pred = len(pred_tasks) - sum(1 for _, p in pairs if p is not None)

    title_tp = sum(1 for _, p in pairs if p is not None)
    title_fn = sum(1 for _, p in pairs if p is None)
    title_fp = unmatched_pred

    assignee_tp = assignee_fp = assignee_fn = 0
    deadline_exact = deadline_near = deadline_total = 0

    for exp, pred in pairs:
        if pred is None:
            if exp.get("assignee"):
                assignee_fn += 1
            if exp.get("deadline"):
                deadline_total += 1
            continue

        ea = _normalize(exp.get("assignee"))
        pa = _normalize(pred.get("assignee"))
        if ea and pa:
            if _title_sim(ea, pa) >= 0.8:
                assignee_tp += 1
            else:
                assignee_fp += 1
                assignee_fn += 1
        elif ea and not pa:
            assignee_fn += 1
        elif not ea and pa:
            assignee_fp += 1

        ed = _parse_date(exp.get("deadline"))
        pd = _parse_date(pred.get("deadline"))
        if ed:
            deadline_total += 1
            if pd:
                if ed == pd:
                    deadline_exact += 1
                    deadline_near += 1
                elif abs((ed - pd).days) <= 1:
                    deadline_near += 1

    exp_conflicts = expected.get("conflicts") or []
    pred_conflicts = predicted.get("conflicts") or []
    exp_ct = {(c.get("type") or c.get("conflict_type", "")) for c in exp_conflicts}
    pred_ct = {(c.get("type") or c.get("conflict_type", "")) for c in pred_conflicts}
    conflict_tp = len(exp_ct & pred_ct)
    conflict_fp = len(pred_ct - exp_ct)
    conflict_fn = len(exp_ct - pred_ct)

    return {
        "title": {"tp": title_tp, "fp": title_fp, "fn": title_fn},
        "assignee": {"tp": assignee_tp, "fp": assignee_fp, "fn": assignee_fn},
        "deadline": {"exact": deadline_exact, "near": deadline_near, "total": deadline_total},
        "conflict": {"tp": conflict_tp, "fp": conflict_fp, "fn": conflict_fn},
    }


def aggregate(per_sample: list[dict]) -> dict:
    """Aggregate per-sample results into overall metrics."""
    t_tp = t_fp = t_fn = 0
    a_tp = a_fp = a_fn = 0
    d_exact = d_near = d_total = 0
    c_tp = c_fp = c_fn = 0

    for s in per_sample:
        t_tp += s["title"]["tp"]; t_fp += s["title"]["fp"]; t_fn += s["title"]["fn"]
        a_tp += s["assignee"]["tp"]; a_fp += s["assignee"]["fp"]; a_fn += s["assignee"]["fn"]
        d_exact += s["deadline"]["exact"]; d_near += s["deadline"]["near"]; d_total += s["deadline"]["total"]
        c_tp += s["conflict"]["tp"]; c_fp += s["conflict"]["fp"]; c_fn += s["conflict"]["fn"]

    return {
        "title_f1": _f1(t_tp, t_fp, t_fn),
        "assignee_f1": _f1(a_tp, a_fp, a_fn),
        "deadline_exact": round(d_exact / d_total, 4) if d_total else 0.0,
        "deadline_near": round(d_near / d_total, 4) if d_total else 0.0,
        "conflict_f1": _f1(c_tp, c_fp, c_fn),
        "counts": {
            "samples": len(per_sample),
            "title_tp": t_tp, "title_fp": t_fp, "title_fn": t_fn,
            "deadline_total": d_total,
        },
    }
