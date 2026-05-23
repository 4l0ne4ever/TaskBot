"""
Evaluation metrics for TaskBot extraction quality.

Compares predicted extraction results against labeled ground truth.
"""
from __future__ import annotations

import os
from difflib import SequenceMatcher
from datetime import date, timedelta

from app.services.assignee_resolver import CANONICAL_MATCH_THRESHOLD, score_names


TITLE_MATCH_THRESHOLD = 0.6
CALIBRATION_BIN_WIDTH = 0.2
CALIBRATION_BIN_COUNT = 5


def _empty_calibration_bins() -> list[dict[str, int]]:
    return [{"n": 0, "correct": 0} for _ in range(CALIBRATION_BIN_COUNT)]


def _record_calibration(bins: list[dict[str, int]], confidence: float, title_match: bool) -> None:
    cf = max(0.0, min(1.0, float(confidence)))
    idx = min(int(cf / CALIBRATION_BIN_WIDTH), CALIBRATION_BIN_COUNT - 1)
    bins[idx]["n"] += 1
    if title_match:
        bins[idx]["correct"] += 1


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _canonical_assignee_for_eval(s: str | None) -> str:
    """Bridge-level normalization for assignee comparison in eval.

    Rationale (Q-05): Vietnamese honorifics are open-ended ("Sếp", "a./c.",
    nicknames, ...), so enumerating them here is an anti-pattern and was
    explicitly called out in review. Production canonicalization is handled by
    the assignee resolver. This helper only removes address-marker punctuation
    that is not part of a name; semantic similarity is delegated to
    ``score_names`` below, which is data-shape based rather than list based.
    """
    if not s or not isinstance(s, str):
        return ""
    t = s.strip()
    while t.startswith("@"):
        t = t[1:].strip()
    return t.strip().lower()


def _title_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _parse_date(v: object) -> date | None:
    if not isinstance(v, str) or not v:
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


def _conflict_eval_skipped(expected: dict, sample: dict | None) -> bool:
    """GT expects inter-doc conflicts but eval did not inject prior tasks — do not score conflict F1."""
    exp_conflicts = expected.get("conflicts") or []
    if not exp_conflicts:
        return False
    if not isinstance(sample, dict):
        return True
    fix = sample.get("eval_existing_tasks")
    return not (isinstance(fix, list) and len(fix) > 0)


# Categories whose deadline gold labels were not curated for deadline accuracy,
# so deadline-exact/near are not scored for them (the tasks/assignee/priority
# scores still count). ``edge_priority`` was authored to test PRIORITY
# extraction: its annotation_notes only record priority, and its deadline
# labels are a placeholder anchor+N that does not track the deadline phrase in
# the text (e.g. text "today" → gold anchor+2) nor the priority level (same
# "GẤP" maps to +1/+2/+3). Scoring deadlines against uncurated labels measures
# the labels, not the model. This is a measurement-scope decision, not a label
# edit — the dataset is left untouched. See docs/quality-issues-tracker.md.
DEADLINE_UNSCORED_CATEGORIES = {"edge_priority"}


def _deadline_eval_skipped(sample: dict | None) -> bool:
    return isinstance(sample, dict) and sample.get("category") in DEADLINE_UNSCORED_CATEGORIES


def evaluate_sample(expected: dict, predicted: dict, sample: dict | None = None) -> dict:
    """Evaluate one sample. Both dicts have 'tasks', 'conflicts', 'missing_fields'.

    When ``sample`` is provided and expected has ``conflicts`` but no non-empty
    ``eval_existing_tasks`` fixture, conflict scores are zero and ``conflict_eval_skipped`` is True.
    """
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

        # Q-05: prefer the resolver-stamped ``assignee_canonical`` when the
        # pipeline produced it (canonical-by-data path), falling back to the
        # rubric-based ``_canonical_assignee_for_eval`` bridge only when the
        # canonical field is absent (old predictions / baselines). Users can
        # disable the canonicalization entirely with
        # ``EVAL_CANONICAL_ASSIGNEE=0`` to stress-test raw prompt output.
        canonical_enabled = os.getenv("EVAL_CANONICAL_ASSIGNEE", "1").lower() not in {"0", "false", "no"}
        if not canonical_enabled:
            ea = _normalize(exp.get("assignee"))
            pa = _normalize(pred.get("assignee"))
        else:
            ea = _normalize(exp.get("assignee_canonical")) or _canonical_assignee_for_eval(exp.get("assignee"))
            pa = _normalize(pred.get("assignee_canonical")) or _canonical_assignee_for_eval(pred.get("assignee"))
        if ea and pa:
            matched = (
                _title_sim(ea, pa) >= 0.8
                if not canonical_enabled
                else score_names(pa, ea) >= CANONICAL_MATCH_THRESHOLD
            )
            if matched:
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

    # Deadline scoring skipped for categories whose deadline labels were not
    # curated for deadline accuracy (see DEADLINE_UNSCORED_CATEGORIES). Zero the
    # counts so these samples are excluded from the deadline denominator without
    # touching the dataset. Title/assignee/priority/conflict still score.
    deadline_eval_skipped = _deadline_eval_skipped(sample)
    if deadline_eval_skipped:
        deadline_exact = deadline_near = deadline_total = 0

    exp_conflicts = expected.get("conflicts") or []
    pred_conflicts = predicted.get("conflicts") or []
    exp_ct = {(c.get("type") or c.get("conflict_type", "")) for c in exp_conflicts}
    pred_ct = {(c.get("type") or c.get("conflict_type", "")) for c in pred_conflicts}
    conflict_tp = len(exp_ct & pred_ct)
    conflict_fp = len(pred_ct - exp_ct)
    conflict_fn = len(exp_ct - pred_ct)
    conflict_eval_skipped = _conflict_eval_skipped(expected, sample)
    if conflict_eval_skipped:
        conflict_tp = conflict_fp = conflict_fn = 0

    exp_empty = len(exp_tasks) == 0
    pred_empty = len(pred_tasks) == 0

    cal_bins = _empty_calibration_bins()
    for exp, pred in pairs:
        if pred is None:
            continue
        c = pred.get("confidence")
        if not isinstance(c, (int, float)):
            continue
        title_ok = _title_sim(exp.get("title", ""), pred.get("title", "")) >= TITLE_MATCH_THRESHOLD
        _record_calibration(cal_bins, float(c), title_ok)

    return {
        "title": {"tp": title_tp, "fp": title_fp, "fn": title_fn},
        "assignee": {"tp": assignee_tp, "fp": assignee_fp, "fn": assignee_fn},
        "deadline": {"exact": deadline_exact, "near": deadline_near, "total": deadline_total},
        "deadline_eval_skipped": deadline_eval_skipped,
        "conflict": {"tp": conflict_tp, "fp": conflict_fp, "fn": conflict_fn},
        "conflict_eval_skipped": conflict_eval_skipped,
        "abstention": {
            "expected_empty": exp_empty,
            "pred_empty": pred_empty,
            "correct_abstain": bool(exp_empty and pred_empty),
            "false_answer_on_empty": bool(exp_empty and not pred_empty),
            "false_abstain_on_nonempty": bool(not exp_empty and pred_empty),
        },
        "calibration_bins": cal_bins,
    }


def aggregate(per_sample: list[dict]) -> dict:
    """Aggregate per-sample results into overall metrics."""
    t_tp = t_fp = t_fn = 0
    a_tp = a_fp = a_fn = 0
    d_exact = d_near = d_total = 0
    c_tp = c_fp = c_fn = 0

    n_exp_empty = correct_abstain = false_answer_empty = 0
    n_exp_nonempty = false_abstain_nonempty = 0
    merged_cal = _empty_calibration_bins()

    c_scoped = 0
    for s in per_sample:
        t_tp += s["title"]["tp"]; t_fp += s["title"]["fp"]; t_fn += s["title"]["fn"]
        a_tp += s["assignee"]["tp"]; a_fp += s["assignee"]["fp"]; a_fn += s["assignee"]["fn"]
        d_exact += s["deadline"]["exact"]; d_near += s["deadline"]["near"]; d_total += s["deadline"]["total"]
        if not s.get("conflict_eval_skipped"):
            co = s["conflict"]
            c_tp += co["tp"]; c_fp += co["fp"]; c_fn += co["fn"]
            c_scoped += 1

        abst = s.get("abstention") or {}
        if abst.get("expected_empty"):
            n_exp_empty += 1
            if abst.get("correct_abstain"):
                correct_abstain += 1
            if abst.get("false_answer_on_empty"):
                false_answer_empty += 1
        else:
            n_exp_nonempty += 1
            if abst.get("false_abstain_on_nonempty"):
                false_abstain_nonempty += 1

        bins = s.get("calibration_bins")
        if not bins or len(bins) != CALIBRATION_BIN_COUNT:
            bins = _empty_calibration_bins()
        for i in range(CALIBRATION_BIN_COUNT):
            merged_cal[i]["n"] += bins[i]["n"]
            merged_cal[i]["correct"] += bins[i]["correct"]

    cal_out: list[dict[str, float | str]] = []
    cal_total_n = sum(x["n"] for x in merged_cal)
    for i, b in enumerate(merged_cal):
        lo = i * CALIBRATION_BIN_WIDTH
        hi = min(1.0, (i + 1) * CALIBRATION_BIN_WIDTH)
        n_b = b["n"]
        acc = round(b["correct"] / n_b, 4) if n_b else 0.0
        cal_out.append(
            {
                "range": f"[{lo:.1f},{hi:.1f})",
                "n": float(n_b),
                "accuracy": acc,
            }
        )

    midpoint = CALIBRATION_BIN_WIDTH / 2.0
    ece_num = 0.0
    for i, b in enumerate(merged_cal):
        n_b = b["n"]
        if n_b:
            acc = b["correct"] / n_b
            conf_mid = min(1.0 - 1e-9, i * CALIBRATION_BIN_WIDTH + midpoint)
            ece_num += abs(acc - conf_mid) * n_b
    ece = round(ece_num / cal_total_n, 4) if cal_total_n else 0.0

    return {
        "title_f1": _f1(t_tp, t_fp, t_fn),
        "assignee_f1": _f1(a_tp, a_fp, a_fn),
        "deadline_exact": round(d_exact / d_total, 4) if d_total else 0.0,
        "deadline_near": round(d_near / d_total, 4) if d_total else 0.0,
        "conflict_f1": _f1(c_tp, c_fp, c_fn),
        "abstention": {
            "when_expected_empty": {
                "samples": n_exp_empty,
                "correct_abstain_rate": round(correct_abstain / n_exp_empty, 4) if n_exp_empty else None,
                "false_answer_rate": round(false_answer_empty / n_exp_empty, 4) if n_exp_empty else None,
            },
            "when_expected_nonempty": {
                "samples": n_exp_nonempty,
                "false_abstain_rate": round(false_abstain_nonempty / n_exp_nonempty, 4) if n_exp_nonempty else None,
            },
        },
        "calibration": {
            "bins": cal_out,
            "ece": ece,
            "confidence_samples": int(cal_total_n),
        },
        "counts": {
            "samples": len(per_sample),
            "title_tp": t_tp, "title_fp": t_fp, "title_fn": t_fn,
            "deadline_total": d_total,
            "conflict_eval_samples_scoped": c_scoped,
            "conflict_eval_samples_skipped": len(per_sample) - c_scoped,
        },
    }
