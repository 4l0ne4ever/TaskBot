#!/usr/bin/env python3
"""
Post-hoc calibration for verbalized confidence (Q-04).

Two methods are fit from a ``run_eval`` JSON artifact (must include
``sample_details`` with ``predicted_tasks`` + ``expected_tasks``):

* ``histogram`` — equal-width binning with Laplace smoothing on empty bins;
  robust for very small ``n``.
* ``isotonic`` — Pool-Adjacent-Violators (Zadrozny & Elkan 2001 / Niculescu-Mizil
  & Caruana 2005): non-parametric monotonic regression on
  ``(raw_confidence, correct)`` pairs. Output is a piecewise-linear mapping
  expressed as knot points; production applies linear interpolation between
  them.

The resulting artifact is **versioned**: it embeds the source eval file path,
its sha256, the fit time, current git sha (when reachable), and
``pairs_used``. Loading the artifact in production is the responsibility of
``agent/app/pipeline/calibration.py``; see ``CALIBRATION_ARTIFACT_PATH``.

Usage:
  python tests/eval/fit_verbalized_calibration.py tests/eval/results/some_run.json \\
    --out tests/eval/results/some_run_calibration.json \\
    --method auto

``auto`` picks ``isotonic`` when ``pairs_used >= ISOTONIC_MIN_N`` (default 30),
otherwise falls back to ``histogram``. This is a practical rule of thumb from
the post-hoc calibration literature: isotonic regression needs a handful of
dozens of points before it beats simple binning on small-sample ECE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from metrics import TITLE_MATCH_THRESHOLD  # noqa: E402

ARTIFACT_SCHEMA_VERSION = 2
ISOTONIC_MIN_N = 30

# Separate threshold for calibration pair generation — must be stricter than
# TITLE_MATCH_THRESHOLD (used for eval recall/precision).  Eval uses 0.6 to
# accept minor wording differences; calibration needs to distinguish genuine
# extractions from hallucinations, so a tighter similarity is required.
# At 0.6 essentially all predicted tasks match some expected task, making the
# (confidence, is_correct) pairs degenerate (all True → PAV maps to 1.0).
# At 0.80 the accuracy signal is non-trivial: e.g. conf=0.80 → 82.6% accuracy
# on the 250-sample eval, giving isotonic PAV real variance to fit against.
CALIBRATION_MATCH_THRESHOLD = 0.80


def _pairs_from_detail(detail: dict) -> list[tuple[float, bool]]:
    """Extract ``(confidence, is_correct)`` pairs from one eval sample.

    For calibration we need both kinds of evidence:

    * A predicted task whose best-matching expected task is similar enough
      (``title_sim >= CALIBRATION_MATCH_THRESHOLD``) is a true positive → ``True``.
    * A predicted task with no sufficiently-similar expected (including the
      case where ``expected_tasks`` is empty for ``email_no_task`` samples)
      is a false positive → ``False``. **This is the signal the prior
      implementation silently dropped**, which made every bin / knot report
      100% accuracy and therefore never shift the confidence scale.

    Expected tasks the model did *not* emit are omitted here — calibration
    acts on the model's own confidence and those rows simply carry no
    confidence to calibrate.

    Note: ``CALIBRATION_MATCH_THRESHOLD`` (0.80) is intentionally stricter than
    the eval metric ``TITLE_MATCH_THRESHOLD`` (0.60). The calibration purpose is
    different — we need to separate hallucinated tasks from real ones, not score
    near-synonymous titles as equivalent for F1 purposes.
    """
    exp = detail.get("expected_tasks") or []
    pred = detail.get("predicted_tasks") or []
    out: list[tuple[float, bool]] = []
    for p in pred:
        if not isinstance(p, dict):
            continue
        c = p.get("confidence")
        if not isinstance(c, (int, float)):
            continue
        p_title = p.get("title", "") or ""
        best_sim = 0.0
        for e in exp:
            if not isinstance(e, dict):
                continue
            sim = _title_sim_local(e.get("title", ""), p_title)
            if sim > best_sim:
                best_sim = sim
        is_correct = best_sim >= CALIBRATION_MATCH_THRESHOLD
        out.append((float(c), bool(is_correct)))
    return out


def _title_sim_local(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    na = (a or "").strip().lower()
    nb = (b or "").strip().lower()
    return SequenceMatcher(None, na, nb).ratio()


def _ece_from_points(points: list[tuple[float, float]]) -> float:
    """ECE-style summary on (raw, target) pairs with 10-bin grid. ``target`` is
    either 0/1 (empirical before) or calibrated-acc (simulated after)."""
    if not points:
        return 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for raw, tgt in points:
        r = max(0.0, min(1.0, raw))
        idx = min(int(r * 10), 9)
        bins[idx].append((r, tgt))
    total = sum(len(b) for b in bins)
    if total == 0:
        return 0.0
    s = 0.0
    for b in bins:
        if not b:
            continue
        mean_raw = sum(r for r, _ in b) / len(b)
        mean_tgt = sum(t for _, t in b) / len(b)
        s += (len(b) / total) * abs(mean_raw - mean_tgt)
    return round(s, 6)


def fit_histogram(points: list[tuple[float, bool]], n_bins: int) -> dict:
    """Equal-width binning with Laplace (+1) smoothing on *empty* bins.

    Laplace smoothing pushes unseen bins toward 0.5 instead of leaving them
    undefined; that keeps the mapping monotone-friendly when fed to the loader
    and avoids a discontinuity where a bin contains no eval data.
    """
    n_bins = max(3, min(20, int(n_bins)))
    raw_bins = [{"lo": i / n_bins, "hi": (i + 1) / n_bins, "n": 0, "correct": 0} for i in range(n_bins)]
    for conf, ok in points:
        conf = max(0.0, min(1.0, float(conf)))
        idx = min(int(conf * n_bins), n_bins - 1)
        raw_bins[idx]["n"] += 1
        if ok:
            raw_bins[idx]["correct"] += 1
    calibrated: list[dict[str, Any]] = []
    for b in raw_bins:
        if b["n"] > 0:
            empirical = b["correct"] / b["n"]
        else:
            empirical = 0.5  # Laplace prior for empty bin
        calibrated.append(
            {
                "lo": b["lo"],
                "hi": b["hi"],
                "n": b["n"],
                "empirical_accuracy": round(empirical, 6),
            }
        )
    return {
        "method": "histogram_binning",
        "n_bins": n_bins,
        "pairs_used": len(points),
        "bins": calibrated,
    }


def fit_isotonic(points: list[tuple[float, bool]]) -> dict:
    """Pool-Adjacent-Violators (PAV) isotonic regression.

    Returns a piecewise-linear monotone mapping encoded as knot points ``[x,
    y]``. In production, linear interpolation between consecutive knots
    gives the calibration curve; outside the observed range we clamp to the
    endpoint values.

    Implementation notes:
      * **Pre-aggregate points with identical ``x``** into a single
        weighted observation before running PAV. Without this step, many
        tied-``x`` points — common with LLM verbalized confidence, which
        often rounds to 0.8/0.9/0.95 — produce a stack of equal-``x``
        knots whose apparent ``y`` depends on input order rather than on
        empirical accuracy.
      * Standard PAV on the aggregated points. Monotonic-regression pooling
        averages two adjacent violators weighted by their aggregate count
        (Barlow & Brunk 1972; Zadrozny & Elkan 2001).
    """
    if not points:
        return {"method": "isotonic", "pairs_used": 0, "knots": [[0.0, 0.0], [1.0, 1.0]]}

    buckets: dict[float, list[int]] = {}
    for c, ok in points:
        x = max(0.0, min(1.0, float(c)))
        buckets.setdefault(x, [0, 0])
        buckets[x][0] += 1
        if ok:
            buckets[x][1] += 1

    xs: list[float] = []
    ys: list[float] = []
    weights: list[float] = []
    for x in sorted(buckets.keys()):
        n, k = buckets[x]
        xs.append(x)
        ys.append(k / n)
        weights.append(float(n))

    i = 0
    while i < len(ys) - 1:
        if ys[i] > ys[i + 1]:
            w = weights[i] + weights[i + 1]
            pooled_y = (ys[i] * weights[i] + ys[i + 1] * weights[i + 1]) / w
            pooled_x = (xs[i] * weights[i] + xs[i + 1] * weights[i + 1]) / w
            ys[i] = pooled_y
            xs[i] = pooled_x
            weights[i] = w
            del ys[i + 1]
            del xs[i + 1]
            del weights[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1

    knots: list[list[float]] = []
    for x, y in zip(xs, ys):
        x_c = round(max(0.0, min(1.0, x)), 6)
        y_c = round(max(0.0, min(1.0, y)), 6)
        knots.append([x_c, y_c])
    if not knots or knots[0][0] > 0.0:
        knots.insert(0, [0.0, knots[0][1] if knots else 0.0])
    if knots[-1][0] < 1.0:
        knots.append([1.0, knots[-1][1]])

    return {
        "method": "isotonic",
        "pairs_used": len(points),
        "knots": knots,
    }


def _apply_histogram(bins: list[dict], x: float) -> float:
    x = max(0.0, min(1.0, float(x)))
    for b in bins:
        if b["lo"] <= x < b["hi"]:
            ea = b.get("empirical_accuracy")
            return float(ea) if ea is not None else x
    return float(bins[-1].get("empirical_accuracy") or x)


def _apply_isotonic(knots: list[list[float]], x: float) -> float:
    x = max(0.0, min(1.0, float(x)))
    if not knots:
        return x
    if x <= knots[0][0]:
        return float(knots[0][1])
    if x >= knots[-1][0]:
        return float(knots[-1][1])
    lo = 0
    hi = len(knots) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if knots[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    x0, y0 = knots[lo]
    x1, y1 = knots[lo + 1]
    if x1 == x0:
        return float(y1)
    return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))


def _ece_before_after(points: list[tuple[float, bool]], fit: dict) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    before_pts = [(c, 1.0 if ok else 0.0) for c, ok in points]
    ece_before = _ece_from_points(before_pts)
    if fit.get("method") == "isotonic":
        after_pts = [(_apply_isotonic(fit.get("knots", []), c), 1.0 if ok else 0.0) for c, ok in points]
    else:
        after_pts = [(_apply_histogram(fit.get("bins", []), c), 1.0 if ok else 0.0) for c, ok in points]
    ece_after = _ece_from_points(after_pts)
    return ece_before, ece_after


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=3.0
        )
        sha = out.stdout.strip()
        return sha or None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _wrap_artifact(fit: dict, *, source_eval: Path, ece_before: float, ece_after: float, method_auto: bool) -> dict:
    artifact: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "fit_time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": _git_sha(),
        "source_eval": str(source_eval),
        "source_eval_sha256": _file_sha256(source_eval) if source_eval.is_file() else None,
        "method_auto_selected": method_auto,
        "ece_before": round(ece_before, 6),
        "ece_after": round(ece_after, 6),
    }
    artifact.update(fit)
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bins", type=int, default=10)
    ap.add_argument("--method", choices=["auto", "histogram", "isotonic"], default="auto")
    args = ap.parse_args()

    data = json.loads(args.eval_json.read_text(encoding="utf-8"))
    details = data.get("sample_details") or []
    points: list[tuple[float, bool]] = []
    for d in details:
        points.extend(_pairs_from_detail(d))

    method = args.method
    method_auto = False
    if method == "auto":
        method_auto = True
        method = "isotonic" if len(points) >= ISOTONIC_MIN_N else "histogram"

    if method == "isotonic":
        fit = fit_isotonic(points)
    else:
        fit = fit_histogram(points, args.bins)

    ece_before, ece_after = _ece_before_after(points, fit)
    artifact = _wrap_artifact(
        fit,
        source_eval=args.eval_json,
        ece_before=ece_before,
        ece_after=ece_after,
        method_auto=method_auto,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
