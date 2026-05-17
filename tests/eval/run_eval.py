#!/usr/bin/env python3
"""
Run evaluation of an extraction method against the labeled dataset.

Outputs:
  1. <output>.json         — full results (overall + per-category + per-sample details)
  2. <output>_report.md    — human-readable markdown report for thesis

  Both are written atomically (temp file then rename) so a crash during write
  does not corrupt the previous JSON/Markdown.

Usage:
  python tests/eval/run_eval.py --method rule     --output tests/eval/results/rule.json
  python tests/eval/run_eval.py --method single   --output tests/eval/results/single_llm.json
  python tests/eval/run_eval.py --method pipeline  --output tests/eval/results/pipeline.json

  Optional: --dataset PATH  (default: tests/eval/labeled_dataset.json)
            --limit N        (only process first N samples)
            --resume PATH    (optional explicit merge source; same contract as implicit resume below)

  Resume / one full run (e.g. 250 samples):
    When the run stops early (daily quota, etc.), the full JSON is still written to ``--output``
    with every ``sample_details`` entry computed so far. Re-running the **same** command
    (same ``--output``, ``--dataset``, ``--limit``, and pipeline policy env) automatically
    loads that file, skips cached ids, runs the rest, and overwrites ``--output`` with the
    merged run. You do not need ``--resume`` unless the merge source is a different path.

  Gemini-only sweep: EVAL_GEMINI_ONLY=1 plus GEMINI_API_KEY (runner sets GROQ_STRICT_PRIMARY for that mode).
  Default pipeline eval uses the same LLM routing as production (primary → fallback → Gemini) unless you set GROQ_STRICT_PRIMARY=1 in .env.

  Strict OSS-only eval + quota resume:
    EVAL_STRICT_PRIMARY_MODEL_ONLY=1 — forces Settings default primary (gpt-oss-120b), GROQ_STRICT_PRIMARY,
    GROQ_DISABLE_GEMINI_FALLBACK (set by pipeline_runner).
    EVAL_ABORT_ON_DAILY_QUOTA=1 (default) — on TPD/RPD hit, stop early and write partial JSON to ``--output``;
    re-run the **same** command to merge (see “Resume / one full run” above). Optional ``--resume PATH`` only if the merge source is not ``--output``.

  Progress logs: EVAL_PROGRESS_EVERY=N (default 1 = log every sample; use 10 for quieter CI).

  If a prior artifact (explicit ``--resume`` or existing ``--output``) records a dataset path,
  it must match the current ``--dataset`` (resolved) or the run exits with an error.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tests" / "eval"))

from metrics import aggregate, evaluate_sample  # noqa: E402

DEFAULT_DATASET = Path(__file__).parent / "labeled_dataset.json"


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``path`` atomically so a crash mid-write never leaves a torn JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def _eval_report_primary_model(method: str) -> str:
    """Model label written to JSON; mirrors eval baseline env resolution (fallback from app.config Field default)."""
    from app.config import Settings

    fb = str(Settings.model_fields["groq_model"].default)
    if method == "pipeline":
        return (os.environ.get("GROQ_MODEL") or "").strip() or fb
    return (os.environ.get("EVAL_GROQ_MODEL") or os.environ.get("GROQ_MODEL") or "").strip() or fb


def _load_dataset(path: Path, limit: int | None = None) -> list[dict]:
    data = json.loads(path.read_text("utf-8"))
    return data[:limit] if limit else data


def _run_rule_based(sample: dict) -> dict:
    from baselines.rule_based import extract_rule_based
    return extract_rule_based(sample["input_text"], sample.get("metadata") or {})


def _run_single_llm(sample: dict) -> dict:
    from baselines.single_llm import extract_single_llm
    return extract_single_llm(sample["input_text"], sample.get("metadata") or {})


def _run_pipeline(sample: dict) -> dict:
    from baselines.pipeline_runner import extract_pipeline

    fixture = sample.get("eval_existing_tasks")
    existing = fixture if isinstance(fixture, list) else None
    sid = sample.get("id")
    trace_id = str(sid) if sid is not None else ""
    return extract_pipeline(
        sample["input_text"],
        sample.get("metadata") or {},
        existing_tasks=existing,
        trace_sample_id=trace_id,
    )


METHODS = {
    "rule": _run_rule_based,
    "single": _run_single_llm,
    "pipeline": _run_pipeline,
}


def _load_resume_artifact(path: Path) -> dict:
    """Load a prior run_eval JSON for --resume (partial or complete)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    details = raw.get("sample_details") or []
    by_id: dict[str, dict] = {}
    for d in details:
        sid = d.get("id")
        if sid is not None:
            by_id[str(sid)] = d
    notes = raw.get("eval_notes") or {}
    ds = raw.get("dataset_info") or {}
    return {
        "details_by_id": by_id,
        "runtime_errors": list(raw.get("runtime_errors") or []),
        "eval_run_id": (notes.get("eval_run_id") or "").strip(),
        "langsmith_session_name": (notes.get("langsmith_session_name") or "").strip(),
        "dataset_path": (ds.get("path") or "").strip(),
    }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _policy_thr_equal(a: str, b: str) -> bool:
    try:
        return round(float(a), 6) == round(float(b), 6)
    except (TypeError, ValueError):
        return (a or "").strip() == (b or "").strip()


def _try_implicit_resume_from_output(
    output: Path,
    *,
    cur_ds: str,
    expected_sample_count: int,
    method: str,
    limit: int | None,
) -> tuple[dict | None, str | None]:
    """If ``output`` is an incomplete prior run for the same job, return artifact dict for merge.

    Returns ``(None, err)`` when a partial on disk cannot be proven compatible (fail-closed: never
    silently overwrite a partial JSON with a fresh run).
    """
    try:
        raw = json.loads(output.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    if (raw.get("method") or "") != method:
        return None, None
    details = raw.get("sample_details") or []
    n = len(details)
    if n == 0 or n >= expected_sample_count:
        return None, None
    ds_info = raw.get("dataset_info") or {}
    ds_path = (ds_info.get("path") or "").strip()
    if not ds_path:
        return (
            None,
            "ERROR: partial --output is missing dataset_info.path; cannot verify dataset. "
            "Fix the JSON or delete it — refusing to overwrite partial results.",
        )
    if Path(ds_path).resolve() != Path(cur_ds).resolve():
        return (
            None,
            f"ERROR: partial --output dataset mismatch: artifact={ds_path!r} current={cur_ds!r}. "
            "Refusing to overwrite partial results.",
        )
    lim_old = ds_info.get("limit_applied")
    if limit is not None and lim_old is not None:
        try:
            if int(lim_old) != int(limit):
                return (
                    None,
                    f"ERROR: partial --output limit_applied={lim_old!r} != current --limit={limit!r}. "
                    "Refusing to overwrite partial results.",
                )
        except (TypeError, ValueError):
            return (
                None,
                f"ERROR: partial --output has invalid dataset_info.limit_applied={lim_old!r}.",
            )
    env_a = (os.getenv("PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE") or "").strip()
    env_u = (os.getenv("PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE") or "").strip()
    pol = raw.get("policy") or {}
    ovr = pol.get("policy_threshold_overrides") or {}
    _ra = ovr.get("abstain")
    _ru = ovr.get("uncertain")
    fa = "" if _ra is None else str(_ra).strip()
    fu = "" if _ru is None else str(_ru).strip()
    if env_a or env_u:
        if not fa or not fu:
            return (
                None,
                "ERROR: existing --output is partial but missing policy_threshold_overrides; "
                "remove the file or use sweep --reset so thresholds are not ambiguous.",
            )
        if not _policy_thr_equal(fa, env_a) or not _policy_thr_equal(fu, env_u):
            return (
                None,
                "ERROR: existing --output partial was produced with different "
                "PIPELINE_POLICY_CONFIDENCE_* overrides; delete that JSON or use a new --output path.",
            )
    return _load_resume_artifact(output), None


def _eval_progress_every() -> int:
    raw = (os.getenv("EVAL_PROGRESS_EVERY") or "1").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 1
    return max(1, n)


def _classify_errors(sample: dict, expected: dict, predicted: dict, scores: dict) -> list[str]:
    """Classify what went wrong for error analysis."""
    issues = []
    if scores["title"]["fn"] > 0:
        issues.append("missed_task")
    if scores["title"]["fp"] > 0:
        issues.append("hallucinated_task")
    if scores["assignee"]["fn"] > 0:
        issues.append("missed_assignee")
    if scores["assignee"]["fp"] > 0:
        issues.append("wrong_assignee")
    if scores["deadline"]["total"] > 0 and scores["deadline"]["exact"] == 0:
        if scores["deadline"]["near"] > 0:
            issues.append("deadline_off_by_one")
        else:
            issues.append("wrong_deadline")
    if scores["conflict"]["fn"] > 0:
        issues.append("missed_conflict")
    if scores["conflict"]["fp"] > 0:
        issues.append("false_conflict")
    if not expected.get("tasks") and predicted.get("tasks"):
        issues.append("false_positive_extraction")
    if expected.get("tasks") and not predicted.get("tasks"):
        issues.append("complete_miss")
    return issues


def _runtime_error_kinds(runtime_errors: list[dict]) -> dict[str, int]:
    """Aggregate runtime errors by ``kind`` so reports / sweep can detect when a
    cell is contaminated by a shared environmental failure (e.g. Groq TPD) vs.
    a real pipeline defect."""
    counts: dict[str, int] = {}
    for item in runtime_errors or []:
        k = str(item.get("kind") or "other")
        counts[k] = counts.get(k, 0) + 1
    return counts


def _build_sample_detail(sample: dict, prediction: dict, scores: dict, error_types: list[str]) -> dict:
    """Build a detailed per-sample record for the report."""
    meta = prediction.get("_meta") if isinstance(prediction, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    return {
        "id": sample.get("id"),
        "category": sample.get("category"),
        "language": sample.get("language"),
        "edge_tags": sample.get("edge_tags"),
        "input_excerpt": sample["input_text"][:200] + ("..." if len(sample["input_text"]) > 200 else ""),
        "expected_task_count": len(sample["expected"].get("tasks") or []),
        "predicted_task_count": len(prediction.get("tasks") or []),
        "expected_tasks": sample["expected"].get("tasks") or [],
        "predicted_tasks": prediction.get("tasks") or [],
        "expected_conflicts": sample["expected"].get("conflicts") or [],
        "eval_existing_tasks_present": bool(sample.get("eval_existing_tasks")),
        "predicted_conflicts": prediction.get("conflicts") or [],
        "scores": scores,
        "error_types": error_types,
        "is_correct": len(error_types) == 0,
        "prediction_meta": meta,
    }


def _generate_report(output: dict, method: str, report_path: Path):
    """Generate a detailed markdown report for thesis use."""
    lines = []
    lines.append(f"# Evaluation Report: {method}")
    lines.append(f"\nGenerated: {datetime.now().isoformat()[:19]}")
    lines.append(f"Dataset: {output['dataset_info']['total_samples']} samples, {output['dataset_info']['total_categories']} categories")
    rt_count = output["runtime_error_count"]
    rt_kinds = output.get("runtime_error_kinds") or {}
    if rt_count and rt_kinds:
        kinds_str = ", ".join(f"{k}={v}" for k, v in sorted(rt_kinds.items(), key=lambda x: -x[1]))
        lines.append(f"Errors (runtime): {rt_count} ({kinds_str})")
    else:
        lines.append(f"Errors (runtime): {rt_count}")

    lines.append("\n## 1. Overall Metrics\n")
    lines.append("| Metric | Precision | Recall | F1 |")
    lines.append("|--------|-----------|--------|----|")
    for field in ["title_f1", "assignee_f1", "conflict_f1"]:
        m = output["overall"][field]
        lines.append(f"| {field.replace('_f1','').capitalize()} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |")
    lines.append(f"\n| Metric | Score |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Deadline Exact Match | {output['overall']['deadline_exact']:.4f} |")
    lines.append(f"| Deadline Near (+-1d) | {output['overall']['deadline_near']:.4f} |")

    abst = output["overall"].get("abstention") or {}
    cal = output["overall"].get("calibration") or {}
    if abst:
        we = abst.get("when_expected_empty") or {}
        wn = abst.get("when_expected_nonempty") or {}
        lines.append("\n| Abstention | Rate |")
        lines.append("|------------|------|")
        car = we.get("correct_abstain_rate")
        far = we.get("false_answer_rate")
        fab = wn.get("false_abstain_rate")
        lines.append(f"| Correct abstain (GT empty) | {car if car is not None else 'n/a'} |")
        lines.append(f"| False answer (GT empty) | {far if far is not None else 'n/a'} |")
        lines.append(f"| False abstain (GT nonempty) | {fab if fab is not None else 'n/a'} |")
    if cal.get("bins"):
        lines.append("\n| Confidence bin | n | Title match acc. |")
        lines.append("|----------------|---|------------------|")
        for b in cal["bins"]:
            if b.get("n", 0):
                lines.append(f"| {b['range']} | {int(b['n'])} | {b['accuracy']:.4f} |")
        lines.append(f"\nECE (vs bin midpoint): **{cal.get('ece', 0):.4f}** (n={cal.get('confidence_samples', 0)} paired w/ confidence)\n")

    lines.append("\n## 2. Per-Category Breakdown\n")
    lines.append("| Category | Samples | Title F1 | Assignee F1 | DL Exact | DL Near | Conflict F1 |")
    lines.append("|----------|---------|----------|-------------|----------|---------|-------------|")
    for cat, data in sorted(output["per_category"].items()):
        n = data["counts"]["samples"]
        tf = data["title_f1"]["f1"]
        af = data["assignee_f1"]["f1"]
        de = data["deadline_exact"]
        dn = data["deadline_near"]
        cf = data["conflict_f1"]["f1"]
        lines.append(f"| {cat} | {n} | {tf:.4f} | {af:.4f} | {de:.4f} | {dn:.4f} | {cf:.4f} |")

    lines.append("\n## 3. Edge Case Performance\n")
    edge_cats = {c: d for c, d in output["per_category"].items() if c.startswith("edge_")}
    core_cats = {c: d for c, d in output["per_category"].items() if not c.startswith("edge_")}
    if edge_cats:
        core_tf = sum(d["title_f1"]["f1"] * d["counts"]["samples"] for d in core_cats.values()) / max(sum(d["counts"]["samples"] for d in core_cats.values()), 1)
        edge_tf = sum(d["title_f1"]["f1"] * d["counts"]["samples"] for d in edge_cats.values()) / max(sum(d["counts"]["samples"] for d in edge_cats.values()), 1)
        lines.append(f"- Core categories weighted Title F1: **{core_tf:.4f}**")
        lines.append(f"- Edge case categories weighted Title F1: **{edge_tf:.4f}**")
        lines.append(f"- Delta: **{edge_tf - core_tf:+.4f}**\n")

    lines.append("## 4. Error Analysis\n")
    err_dist = output.get("error_type_distribution") or {}
    if err_dist:
        lines.append("| Error Type | Count | % of Samples |")
        lines.append("|------------|-------|--------------|")
        total = output["overall"]["counts"]["samples"]
        for etype, cnt in sorted(err_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {etype} | {cnt} | {cnt/total*100:.1f}% |")

    lines.append("\n## 5. Per-Category Error Heatmap\n")
    cat_err: dict[str, dict[str, int]] = {}
    for detail in output.get("sample_details", []):
        cat = detail["category"]
        for et in detail.get("error_types", []):
            cat_err.setdefault(cat, {}).setdefault(et, 0)
            cat_err[cat][et] += 1
    all_err_types = sorted({et for ce in cat_err.values() for et in ce})
    if all_err_types:
        header = "| Category | " + " | ".join(all_err_types) + " |"
        sep = "|----------|" + "|".join(["---"] * len(all_err_types)) + "|"
        lines.append(header)
        lines.append(sep)
        for cat in sorted(cat_err.keys()):
            vals = " | ".join(str(cat_err[cat].get(et, 0)) for et in all_err_types)
            lines.append(f"| {cat} | {vals} |")

    lines.append("\n## 6. Sample-Level Details (Errors Only)\n")
    error_details = [d for d in output.get("sample_details", []) if not d["is_correct"]]
    for d in error_details[:50]:
        lines.append(f"### {d['id']} ({d['category']}, {d['language']})")
        if d.get("edge_tags"):
            lines.append(f"Edge tags: {', '.join(d['edge_tags'])}")
        lines.append(f"\n**Input:** {d['input_excerpt']}\n")
        lines.append(f"**Expected tasks:** {len(d['expected_tasks'])} | **Predicted:** {len(d['predicted_tasks'])}")
        if d["expected_tasks"]:
            for t in d["expected_tasks"]:
                lines.append(f"  - E: \"{t.get('title')}\" | {t.get('assignee')} | {t.get('deadline')} | pri={t.get('priority')}")
        if d["predicted_tasks"]:
            for t in d["predicted_tasks"]:
                lines.append(f"  - P: \"{t.get('title')}\" | {t.get('assignee')} | {t.get('deadline')} | pri={t.get('priority')}")
        lines.append(f"\n**Errors:** {', '.join(d['error_types'])}")
        lines.append(f"**Scores:** title={d['scores']['title']}, assignee={d['scores']['assignee']}, deadline={d['scores']['deadline']}, conflict={d['scores']['conflict']}")
        lines.append("")

    if len(error_details) > 50:
        lines.append(f"\n_...and {len(error_details) - 50} more error samples (see JSON for full details)._\n")

    lines.append(f"\n## 7. Summary Statistics\n")
    correct = sum(1 for d in output.get("sample_details", []) if d["is_correct"])
    total = len(output.get("sample_details", []))
    if total:
        lines.append(f"- Fully correct samples: **{correct}/{total}** ({correct/total*100:.1f}%)")
        lines.append(f"- Samples with errors: **{total - correct}/{total}** ({(total-correct)/total*100:.1f}%)")
    else:
        lines.append("- Fully correct samples: **0/0** (no samples in this report)")
        lines.append("- Samples with errors: **0/0**")

    _atomic_write_text(report_path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="TaskBot Extraction Evaluation")
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Existing run_eval JSON: skip samples already present in sample_details (same dataset order/ids).",
    )
    args = parser.parse_args()
    cur_ds = str(args.dataset.resolve()) if args.dataset.is_absolute() else str((ROOT / args.dataset).resolve())

    samples = _load_dataset(args.dataset, args.limit)
    expected_n = len(samples)

    resume_artifact: dict | None = None
    resume_path_resolved: str | None = None
    if args.resume:
        rp = args.resume if args.resume.is_absolute() else ROOT / args.resume
        if not rp.is_file():
            print(f"ERROR: --resume file not found: {rp}", file=sys.stderr, flush=True)
            return 2
        resume_artifact = _load_resume_artifact(rp)
        resume_path_resolved = str(rp.resolve())
        prev_ds = resume_artifact.get("dataset_path") or ""
        if prev_ds and Path(prev_ds).resolve() != Path(cur_ds).resolve():
            print(
                f"ERROR: --resume dataset mismatch: artifact={prev_ds!r} current={cur_ds!r}.",
                file=sys.stderr,
                flush=True,
            )
            return 2
    elif args.output.is_file():
        implicit, err = _try_implicit_resume_from_output(
            args.output,
            cur_ds=cur_ds,
            expected_sample_count=expected_n,
            method=args.method,
            limit=args.limit,
        )
        if err:
            print(err, file=sys.stderr, flush=True)
            return 2
        if implicit:
            resume_artifact = implicit
            resume_path_resolved = str(args.output.resolve())

    extract_fn = METHODS[args.method]

    eval_run_id = ""
    langsmith_session = ""
    if args.method == "pipeline":
        existing_rid = (os.getenv("EVAL_RUN_ID") or "").strip()
        existing_sess = (os.getenv("LANGSMITH_SESSION_NAME") or "").strip()
        if resume_artifact and resume_artifact.get("eval_run_id") and not existing_rid:
            eval_run_id = resume_artifact["eval_run_id"]
            os.environ["EVAL_RUN_ID"] = eval_run_id
        elif existing_rid:
            eval_run_id = existing_rid
        else:
            eval_run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
            os.environ["EVAL_RUN_ID"] = eval_run_id
        if resume_artifact and resume_artifact.get("langsmith_session_name") and not existing_sess:
            langsmith_session = resume_artifact["langsmith_session_name"]
            os.environ["LANGSMITH_SESSION_NAME"] = langsmith_session
        elif existing_sess:
            langsmith_session = existing_sess
        else:
            langsmith_session = f"eval-pipeline-{eval_run_id}"
            os.environ["LANGSMITH_SESSION_NAME"] = langsmith_session
        print(f"EVAL_RUN_ID={eval_run_id}", flush=True)
        print(f"LANGSMITH_SESSION_NAME={langsmith_session} (filter runs in LangSmith)", flush=True)

    sample_details: list[dict] = []
    runtime_errors: list[dict] = list(resume_artifact["runtime_errors"]) if resume_artifact else []
    details_by_id: dict[str, dict] = dict(resume_artifact["details_by_id"]) if resume_artifact else {}
    if resume_artifact:
        print(f"  RESUME: {len(details_by_id)} cached sample(s); running only missing ids.", flush=True)

    stop_requested = False
    stop_signal: str | None = None

    def _request_stop(sig_name: str) -> None:
        nonlocal stop_requested, stop_signal
        stop_requested = True
        stop_signal = sig_name

    def _handle_signal(signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        name = getattr(signal.Signals(signum), "name", str(signum))
        _request_stop(name)

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        # Best-effort: signal hooks are not critical in all environments.
        pass

    def _classify_runtime_error(msg: str) -> str:
        """Tag runtime errors with a coarse kind so downstream tooling (sweep,
        quality-gate) can decide whether a cell is *measurement-contaminated*
        by a transient environmental issue vs. a real pipeline defect.

        Daily-quota (TPD/RPD) exhaustion is the dominant contaminant observed
        on Groq free tier: the sample produces no prediction, which collapses
        into FN in title/assignee F1 regardless of which policy threshold is
        being evaluated. Treat it as a distinct class so the sweep can flag
        the whole cell rather than silently averaging over a shared failure
        mode. (See docs/quality-issues-tracker.md pass 6/7 notes.)
        """
        lower = (msg or "").lower()
        if ("per minute" in lower) or ("(rpm)" in lower) or ("tokens per minute" in lower):
            return "rate_limit_other"
        if ("daily quota" in lower) or ("tpd" in lower) or ("rpd" in lower):
            return "daily_quota"
        if ("per day" in lower) and ("quota" in lower or "limit" in lower):
            return "daily_quota"
        if "resource exhausted" in lower or "resourceexhausted" in lower.replace(" ", ""):
            return "daily_quota"
        if "quota" in lower and ("exceed" in lower or "exhausted" in lower):
            return "daily_quota"
        if ("rate_limit" in lower) or ("rate limit" in lower) or ("429" in lower):
            return "rate_limit_other"
        if "organization has been restricted" in lower or "organization_restricted" in lower.replace(" ", "_"):
            return "organization_restricted"
        if "invalid_request_error" in lower and "restricted" in lower and "organization" in lower:
            return "organization_restricted"
        return "other"

    total = expected_n
    processed_samples: list[dict] = []
    aborted_early = False
    abort_reason: str | None = None
    abort_after_samples: int | None = None
    abort_on_daily_quota = args.method == "pipeline" and _env_flag("EVAL_ABORT_ON_DAILY_QUOTA", True)
    abort_on_org_restricted = args.method == "pipeline" and _env_flag(
        "EVAL_ABORT_ON_ORGANIZATION_RESTRICTED", True
    )
    prog_every = _eval_progress_every()

    def _should_log_progress(i: int) -> bool:
        return i == 0 or (i + 1) % prog_every == 0

    for i, sample in enumerate(samples):
        sid = sample.get("id")
        sid_key = str(sid) if sid is not None else ""
        if sid_key and sid_key in details_by_id:
            if _should_log_progress(i):
                print(f"  [{i+1}/{total}] resume skip {sid} ({sample.get('category')}) [cached]", flush=True)
            sample_details.append(details_by_id[sid_key])
            processed_samples.append(sample)
            continue

        if stop_requested:
            aborted_early = True
            abort_reason = "signal"
            abort_after_samples = i
            print(
                f"  ABORT: stop requested ({stop_signal}); will write partial JSON to --output then exit.",
                flush=True,
            )
            break

        if _should_log_progress(i):
            print(f"  [{i+1}/{total}] processing {sample.get('id')} ({sample.get('category')})...", flush=True)
        runtime_kind: str | None = None
        try:
            prediction = extract_fn(sample)
        except Exception as exc:
            runtime_kind = _classify_runtime_error(str(exc))
            runtime_errors.append(
                {
                    "index": i,
                    "id": sample.get("id"),
                    "error": str(exc),
                    "kind": runtime_kind,
                }
            )
            prediction = {"tasks": [], "conflicts": [], "missing_fields": []}

        scores = evaluate_sample(sample["expected"], prediction, sample)
        error_types = _classify_errors(sample, sample["expected"], prediction, scores)

        detail = _build_sample_detail(sample, prediction, scores, error_types)
        prov = ((prediction.get("_meta") or {}).get("model_provenance")) if isinstance(prediction, dict) else None
        if isinstance(prov, dict):
            detail["model_provenance"] = prov
        sample_details.append(detail)
        processed_samples.append(sample)

        if runtime_kind == "daily_quota" and abort_on_daily_quota:
            aborted_early = True
            abort_reason = "daily_quota"
            abort_after_samples = i + 1
            print(
                "  ABORT: daily quota (TPD/RPD) exhausted; will write partial JSON to --output then exit.",
                flush=True,
            )
            break

        if runtime_kind == "organization_restricted" and abort_on_org_restricted:
            aborted_early = True
            abort_reason = "organization_restricted"
            abort_after_samples = i + 1
            print(
                "  ABORT: Groq organization restricted (account/API); partial JSON written; "
                "fix access with Groq support or another key — remaining samples would only duplicate this failure.",
                flush=True,
            )
            break

        if stop_requested:
            aborted_early = True
            abort_reason = "signal"
            abort_after_samples = i + 1
            print(
                f"  ABORT: stop requested ({stop_signal}); will write partial JSON to --output then exit.",
                flush=True,
            )
            break

        if args.method == "pipeline":
            every = int(os.getenv("EVAL_BATCH_COOLDOWN_EVERY", "20"))
            pause_sec = float(os.getenv("EVAL_BATCH_COOLDOWN_SECONDS", "45"))
            if every > 0 and pause_sec > 0 and (i + 1) % every == 0 and (i + 1) < total:
                print(
                    f"  ... batch cooldown {pause_sec}s after {i + 1}/{total} samples (rate-limit hygiene)",
                    flush=True,
                )
                time.sleep(pause_sec)

    error_type_dist: dict[str, int] = {}
    for d in sample_details:
        for et in d.get("error_types") or []:
            error_type_dist[et] = error_type_dist.get(et, 0) + 1

    provenance_per_sample: list[dict] = []
    for d in sample_details:
        prov = d.get("model_provenance")
        if isinstance(prov, dict):
            provenance_per_sample.append({"sample_id": d.get("id"), **prov})

    per_sample_scores = [
        {
            "title": d["scores"]["title"],
            "assignee": d["scores"]["assignee"],
            "deadline": d["scores"]["deadline"],
            "conflict": d["scores"]["conflict"],
            "conflict_eval_skipped": d["scores"].get("conflict_eval_skipped", False),
            "abstention": d["scores"]["abstention"],
            "calibration_bins": d["scores"]["calibration_bins"],
            "sample_id": d["id"],
            "category": d["category"],
        }
        for d in sample_details
    ]
    overall = aggregate(per_sample_scores)
    _counts = overall.get("counts") or {}

    by_cat: dict[str, list[dict]] = {}
    for s in per_sample_scores:
        by_cat.setdefault(s["category"], []).append(s)

    model_stats = {}
    if args.method == "single":
        try:
            from baselines.single_llm import get_model_stats
            model_stats = get_model_stats()
        except ImportError:
            pass
    elif args.method == "pipeline":
        try:
            from app.pipeline.llm import get_fallback_count
            model_stats = {"fallback_calls": get_fallback_count()}
        except ImportError:
            pass
        if provenance_per_sample:
            total_primary = sum(int(p.get("primary_calls") or 0) for p in provenance_per_sample)
            total_fallback = sum(int(p.get("fallback_calls") or 0) for p in provenance_per_sample)
            total_rl = sum(int(p.get("rate_limited_calls") or 0) for p in provenance_per_sample)
            contam_samples = sum(1 for p in provenance_per_sample if p.get("contaminated"))
            model_mix: dict[str, int] = {}
            for p in provenance_per_sample:
                for mname, cnt in (p.get("models_used") or {}).items():
                    model_mix[mname] = model_mix.get(mname, 0) + int(cnt)
            model_stats.update(
                {
                    "primary_calls_total": total_primary,
                    "fallback_calls_per_sample_total": total_fallback,
                    "rate_limited_calls_total": total_rl,
                    "samples_using_fallback": contam_samples,
                    "samples_total_with_provenance": len(provenance_per_sample),
                    "contaminated": contam_samples > 0,
                    "model_mix": model_mix,
                    "strict_primary_mode": (os.getenv("GROQ_STRICT_PRIMARY") or "").strip().lower()
                    in {"1", "true", "yes", "on"},
                }
            )

    eval_model = _eval_report_primary_model(args.method)
    samples_with_eval_existing = sum(
        1 for s in processed_samples if isinstance(s.get("eval_existing_tasks"), list)
    )
    eval_notes = {
        "samples_with_eval_existing_tasks": samples_with_eval_existing,
        "conflict_eval_samples_skipped_for_metric": _counts.get("conflict_eval_samples_skipped"),
        "conflict_eval_samples_included_in_aggregate": _counts.get("conflict_eval_samples_scoped"),
        "conflict_metrics_note": (
            "Conflict F1 is aggregated only for samples that are not conflict_eval_skipped: "
            "GT conflict rows without a non-empty eval_existing_tasks fixture are excluded so the metric is not "
            "artificially zero. Rows with a fixture exercise validate-node conflict detection."
        ),
        "eval_run_id": eval_run_id or None,
        "langsmith_session_name": langsmith_session or None,
        "strict_primary_model_only": _env_flag("EVAL_STRICT_PRIMARY_MODEL_ONLY", False),
        "aborted_early": aborted_early,
        "abort_reason": abort_reason,
        "abort_after_samples": abort_after_samples,
        "resume_source_path": resume_path_resolved,
        "resume_cached_samples_at_start": len(details_by_id) if resume_artifact else 0,
        "langsmith_hint": (
            "Each LLM call is logged as groq_chat_completion; each document as pipeline_run_trace. "
            "Filter by session name above; per-sample via inputs.sample_id."
        )
        if args.method == "pipeline"
        else None,
    }
    policy_effective: dict | None = None
    if args.method == "pipeline":
        try:
            sys.path.insert(0, str(ROOT / "agent"))
            from app.pipeline.policy import get_pipeline_policy

            pol = get_pipeline_policy()
            ver = (os.getenv("PIPELINE_POLICY_VERSION") or "v1").strip().lower()
            if ver.startswith("policy_"):
                ver = ver[7:]
            policy_effective = {
                "pipeline_policy_version_key": ver,
                "confidence_abstain_threshold": pol.confidence_abstain_threshold,
                "confidence_uncertain_threshold": pol.confidence_uncertain_threshold,
                "max_conflict_checks_per_task": pol.max_conflict_checks_per_task,
                "policy_version_label": pol.version,
            }
        except Exception as exc:
            policy_effective = {"load_error": str(exc)}

    _abst_ov = (os.getenv("PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE") or "").strip()
    _unc_ov = (os.getenv("PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE") or "").strip()
    policy_meta = {
        "pipeline_policy_version": os.getenv("PIPELINE_POLICY_VERSION"),
        "policy_threshold_overrides": {
            "abstain": _abst_ov or None,
            "uncertain": _unc_ov or None,
        },
        "cost_control_overrides": {
            "max_conflict_checks": os.getenv("PIPELINE_POLICY_MAX_CONFLICT_CHECKS_OVERRIDE"),
            "eval_enable_conflict_check": os.getenv("EVAL_ENABLE_CONFLICT_CHECK"),
            "extraction_max_retries": os.getenv("EXTRACTION_MAX_RETRIES"),
        },
        "effective": policy_effective,
    }

    output = {
        "method": args.method,
        "eval_model": eval_model,
        "policy": policy_meta,
        "model_stats": model_stats,
        "timestamp": datetime.now().isoformat(),
        "dataset_info": {
            "path": cur_ds,
            "total_samples": len(processed_samples),
            "requested_samples": len(samples),
            "total_categories": len(by_cat),
            "limit_applied": args.limit,
        },
        "eval_notes": eval_notes,
        "aborted_early": aborted_early,
        "abort_reason": abort_reason,
        "abort_after_samples": abort_after_samples,
        "overall": overall,
        "per_category": {cat: aggregate(items) for cat, items in sorted(by_cat.items())},
        "error_type_distribution": dict(sorted(error_type_dist.items(), key=lambda x: -x[1])),
        "runtime_errors": runtime_errors,
        "runtime_error_count": len(runtime_errors),
        "runtime_error_kinds": _runtime_error_kinds(runtime_errors),
        "sample_details": sample_details,
    }

    _atomic_write_text(args.output, json.dumps(output, ensure_ascii=False, indent=2))
    if aborted_early:
        print(
            f"  Wrote partial JSON ({len(sample_details)}/{len(samples)} samples) -> {args.output}",
            flush=True,
        )

    report_path = args.output.with_name(args.output.stem + "_report.md")
    _generate_report(output, args.method, report_path)

    print(f"Method: {args.method}  Model: {eval_model}  {model_stats if model_stats else ''}")
    print(f"Samples: {overall['counts']['samples']}  Runtime errors: {len(runtime_errors)}")
    print(f"Title F1:       {overall['title_f1']['f1']:.4f}  (P={overall['title_f1']['precision']:.4f} R={overall['title_f1']['recall']:.4f})")
    print(f"Assignee F1:    {overall['assignee_f1']['f1']:.4f}")
    print(f"Deadline Exact: {overall['deadline_exact']:.4f}")
    print(f"Deadline Near:  {overall['deadline_near']:.4f}")
    print(f"Conflict F1:    {overall['conflict_f1']['f1']:.4f}")
    if overall.get("abstention"):
        ae = overall["abstention"].get("when_expected_empty") or {}
        an = overall["abstention"].get("when_expected_nonempty") or {}
        print(
            f"Abstention: correct_abstain(empty GT)={ae.get('correct_abstain_rate')} "
            f"false_answer(empty GT)={ae.get('false_answer_rate')} "
            f"false_abstain(nonempty GT)={an.get('false_abstain_rate')}"
        )
    if overall.get("calibration"):
        print(f"Calibration ECE: {overall['calibration'].get('ece')}  (confidence pairs: {overall['calibration'].get('confidence_samples', 0)})")
    correct = sum(1 for d in sample_details if d["is_correct"])
    denom = len(sample_details) or 1
    print(f"Fully correct:  {correct}/{len(sample_details)} ({correct/denom*100:.1f}%)")
    print(f"\nTop error types:")
    for et, cnt in sorted(error_type_dist.items(), key=lambda x: -x[1])[:5]:
        print(f"  {et}: {cnt}")
    print(f"\nJSON:   {args.output}")
    print(f"Report: {report_path}")
    if args.method == "pipeline":
        try:
            sys.path.insert(0, str(ROOT / "agent"))
            from app.services.observability import calculate_slo_snapshot

            slo = calculate_slo_snapshot()
            print(f"Redis LLM SLO snapshot (last N calls): {slo}")
        except Exception as exc:
            print(f"(optional) Redis SLO snapshot skipped: {exc}", flush=True)
    if aborted_early and not _env_flag("EVAL_ABORT_EXIT_ZERO", False):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
