#!/usr/bin/env python3
"""
Sweep confidence policy thresholds on a labeled split and write a CSV artifact.

Methodology (see docs/quality-issues-tracker.md Q-07):
  For each (abstain, uncertain) grid point, run pipeline eval with env overrides
  PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE / UNCERTAIN_OVERRIDE and record metrics.

Checkpoint / resume:
  * Sweep-level ``--resume``: reload ``--checkpoint`` and skip grid cells that
    already finished (no ``aborted_early``).
  * Sample-level (same 250-sample run): ``run_eval`` writes the full JSON to each
    cell's ``--output`` path. That file is **always kept** when the cell finishes
    (clean or partial) so you can inspect metrics, run ``sweep_policy_thresholds_offline.py``,
    or audit ``sample_details``. The next subprocess reuses the same path and
    ``run_eval`` merges cached ``sample_details`` for incomplete runs (no extra
    ``--resume`` flag required).

  Fresh grid: ``--reset`` clears checkpoint, CSV, and ``_sweep_a*.json`` artifacts
  (do not combine with sweep ``--resume``).

Usage:
  PIPELINE_POLICY_VERSION=v2 python tests/eval/sweep_policy_thresholds.py \\
    --output tests/eval/policy_freeze/sweep_v2.csv \\
    --checkpoint tests/eval/policy_freeze/sweep_v2_checkpoint.json \\
    --write-freeze tests/eval/policy_freeze/chosen_v2.json --limit 40

  # After pause / 429:
  ... same command ... --resume

Requires .env with Groq + DB URLs (same as run_eval pipeline).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import atexit
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_LOCK_PATH: Path | None = None


def _default_abstain_grid() -> list[str]:
    raw = os.getenv("EVAL_SWEEP_ABSTAIN_GRID", "0.55,0.6,0.65")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _default_uncertain_grid() -> list[str]:
    raw = os.getenv("EVAL_SWEEP_UNCERTAIN_GRID", "0.76,0.8,0.84")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _cell_key(a: str, u: str) -> str:
    return f"{round(float(a), 6)!s}|{round(float(u), 6)!s}"


def _allow_contaminated() -> bool:
    return (os.getenv("EVAL_SWEEP_ALLOW_CONTAMINATED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _disable_lock() -> bool:
    return (os.getenv("EVAL_SWEEP_DISABLE_LOCK", "0") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _lock_path_for(checkpoint_path: Path) -> Path:
    return checkpoint_path.with_suffix(checkpoint_path.suffix + ".lock")


def _release_lock(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _acquire_lock(path: Path) -> None:
    global _ACTIVE_LOCK_PATH
    if _disable_lock():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "started_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": os.uname().nodename,
    }
    try:
        # O_EXCL makes lock acquisition atomic and fail-fast.
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise SystemExit(
            f"sweep lock exists at {path}. Another sweep may be running with the same checkpoint/output. "
            "Wait for it to finish or remove stale lock explicitly."
        )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    _ACTIVE_LOCK_PATH = path


def _cleanup_active_lock() -> None:
    global _ACTIVE_LOCK_PATH
    if _ACTIVE_LOCK_PATH is not None:
        _release_lock(_ACTIVE_LOCK_PATH)
        _ACTIVE_LOCK_PATH = None


atexit.register(_cleanup_active_lock)


def _require_clean_candidate() -> bool:
    return (os.getenv("EVAL_SWEEP_REQUIRE_CLEAN_CANDIDATE", "1") or "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _stop_on_daily_quota() -> bool:
    return (os.getenv("EVAL_SWEEP_STOP_ON_DAILY_QUOTA", "1") or "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _stop_on_organization_restricted() -> bool:
    return (os.getenv("EVAL_SWEEP_STOP_ON_ORGANIZATION_RESTRICTED", "1") or "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _row_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "abstain",
        "uncertain",
        "title_f1",
        "deadline_exact",
        "fully_correct_pct",
        "correct_abstain_empty_gt",
        "false_answer_empty_gt",
        "ece",
        "fallback_calls",
        "samples_using_fallback",
        "rate_limited_calls",
        "strict_primary_mode",
        "runtime_error_count",
        "runtime_error_kinds",
        "aborted_early",
        "abort_reason",
        "samples_completed",
        "samples_requested",
        "contaminated",
        "contaminated_reason",
    ]
    seen = set()
    names: list[str] = []
    for name in preferred:
        if any(name in r for r in rows):
            names.append(name)
            seen.add(name)
    for row in rows:
        for name in row:
            if name not in seen:
                names.append(name)
                seen.add(name)
    return names


def _runtime_contamination_threshold(total_samples: int) -> int:
    """How many runtime errors may a cell have before we flag it as
    *measurement-contaminated*.

    Any runtime error collapses a sample's prediction into ``{"tasks": []}`` and
    the evaluator counts it as FN in title/assignee F1. When the cause is a
    shared environmental failure (Groq TPD, transport error, DB hiccup), the
    metric penalty has nothing to do with the policy threshold under test —
    different cells would see wildly different F1 depending on how many
    "environmental" samples happened to land in that cell.

    We therefore treat a cell as contaminated when the runtime-error rate
    exceeds the tolerance (default 10% of samples, minimum 2). Users can tune
    via ``EVAL_SWEEP_RUNTIME_TOLERANCE`` (0.0–1.0) or, as a crude kill-switch,
    ``EVAL_SWEEP_ALLOW_RUNTIME_ERRORS=1`` to keep the old behaviour.
    """
    if not total_samples:
        return 0
    raw = os.getenv("EVAL_SWEEP_RUNTIME_TOLERANCE", "0.1")
    try:
        tol = max(0.0, min(1.0, float(raw)))
    except ValueError:
        tol = 0.1
    return max(2, int(round(total_samples * tol)))


def _classify_contamination(
    *,
    fb_samples: int,
    runtime_count: int,
    runtime_kinds: dict[str, int] | None,
    total_samples: int,
) -> tuple[bool, str | None]:
    """Return (contaminated, reason). Reason is the dominant contamination kind
    so operators can triage (``"fallback"`` → tier mix; ``"runtime_tpd"`` → quota
    reset; ``"runtime_other"`` → investigate underlying exception)."""
    if fb_samples > 0:
        return True, "fallback"
    if runtime_count == 0:
        return False, None
    if (os.getenv("EVAL_SWEEP_ALLOW_RUNTIME_ERRORS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False, None
    if runtime_count < _runtime_contamination_threshold(total_samples):
        return False, None
    kinds = dict(runtime_kinds or {})
    if kinds.get("daily_quota", 0) >= max(1, runtime_count // 2):
        return True, "runtime_tpd"
    if kinds.get("rate_limit_other", 0) >= max(1, runtime_count // 2):
        return True, "runtime_rate_limit"
    if kinds.get("organization_restricted", 0) >= max(1, runtime_count // 2):
        return True, "runtime_org_restricted"
    return True, "runtime_other"


def _pick_best_row(
    rows: list[dict[str, Any]],
    *,
    cost_fp: float,
) -> dict[str, Any] | None:
    """Maximize ``title_f1 - cost_fp * false_answer`` on the empty-GT bucket.

    Rows flagged ``contaminated=True`` (i.e. the eval cell mixed primary and
    fallback model outputs) are excluded by default: a sweep cell whose
    measurements were partly produced by a different model is a confounded
    experiment and cannot be fairly compared to clean cells. Set
    ``EVAL_SWEEP_ALLOW_CONTAMINATED=1`` to include them anyway.
    """
    if not rows:
        return None
    allow_contam = _allow_contaminated()
    candidates = rows if allow_contam else [r for r in rows if not r.get("contaminated")]
    if not candidates:
        return None
    best: dict[str, Any] | None = None
    best_key: tuple[float, float, float] = (-1.0, -1.0, -1.0)
    for r in candidates:
        tf = float(r.get("title_f1") or 0.0)
        fa_raw = r.get("false_answer_empty_gt")
        fa = float(fa_raw) if fa_raw is not None else 0.0
        score = tf - cost_fp * fa
        fcp = float(r.get("fully_correct_pct") or 0.0)
        key = (score, tf, fcp)
        if key > best_key:
            best_key = key
            best = r
    return best


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_freeze_artifact(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(path, payload)


def _fully_correct_pct(payload: dict) -> float:
    details = payload.get("sample_details") or []
    if not details:
        return 0.0
    ok = sum(1 for d in details if d.get("is_correct"))
    return round(100.0 * ok / len(details), 2)


def _load_checkpoint(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(path, payload)


def _reset_sweep_artifacts(checkpoint_path: Path, output_csv: Path, cell_dir: Path) -> None:
    """Remove checkpoint, CSV, per-cell JSON/reports, and sweep lock for a clean grid run."""
    _release_lock(_lock_path_for(checkpoint_path))
    checkpoint_path.unlink(missing_ok=True)
    output_csv.unlink(missing_ok=True)
    for pattern in ("_sweep_a*.json", "_sweep_a*_report.md"):
        for p in cell_dir.glob(pattern):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def _validate_resume(
    cp: dict[str, Any],
    *,
    dataset: Path,
    limit: int | None,
    abstain_vals: list[str],
    uncertain_vals: list[str],
    policy_ver: str,
) -> None:
    ds_cp = Path(cp.get("dataset") or "")
    if not ds_cp.is_absolute():
        ds_cp = ROOT / ds_cp
    if dataset.resolve() != ds_cp.resolve():
        raise SystemExit(
            f"Checkpoint dataset mismatch: checkpoint={ds_cp} current={dataset.resolve()}. "
            "Use the same --dataset or a fresh --checkpoint path."
        )
    if cp.get("limit") != limit:
        raise SystemExit(f"Checkpoint limit={cp.get('limit')} != current --limit={limit}")
    if [str(x) for x in cp.get("abstain_grid") or []] != abstain_vals:
        raise SystemExit("Checkpoint abstain_grid does not match current grid (check EVAL_SWEEP_ABSTAIN_GRID / --abstain).")
    if [str(x) for x in cp.get("uncertain_grid") or []] != uncertain_vals:
        raise SystemExit("Checkpoint uncertain_grid does not match current grid.")
    if str(cp.get("pipeline_policy_version") or "").strip() != policy_ver.strip():
        raise SystemExit(
            f"Checkpoint pipeline_policy_version={cp.get('pipeline_policy_version')!r} != {policy_ver!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep policy thresholds via pipeline eval")
    parser.add_argument("--output", type=Path, required=True, help="CSV path for results grid")
    parser.add_argument("--dataset", type=Path, default=ROOT / "tests" / "eval" / "labeled_dataset.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--abstain", type=str, default=None, help="Comma-separated; default from EVAL_SWEEP_ABSTAIN_GRID")
    parser.add_argument("--uncertain", type=str, default=None, help="Comma-separated; default from EVAL_SWEEP_UNCERTAIN_GRID")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="JSON path for resume state (default: <output_stem>_checkpoint.json next to --output)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from --checkpoint (skip already completed abstain/uncertain pairs)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete checkpoint, CSV, _sweep_a*.json and _sweep_a*_report.md next to --output, then start a new grid (mutually exclusive with --resume).",
    )
    parser.add_argument(
        "--write-freeze",
        type=Path,
        default=None,
        help="Write JSON with winning cell after full grid completes (partial sweeps skip this unless all cells done)",
    )
    args = parser.parse_args()

    abstain_vals = [x.strip() for x in args.abstain.split(",")] if args.abstain else _default_abstain_grid()
    uncertain_vals = [x.strip() for x in args.uncertain.split(",")] if args.uncertain else _default_uncertain_grid()
    dataset = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    policy_ver = (os.getenv("PIPELINE_POLICY_VERSION") or "v1").strip()
    cost_fp = float(os.getenv("EVAL_SWEEP_COST_FP_NO_TASK", "1"))
    cost_fn = float(os.getenv("EVAL_SWEEP_COST_FN_TASK", "1"))

    checkpoint_path = args.checkpoint
    if checkpoint_path is None:
        checkpoint_path = args.output.parent / f"{args.output.stem}_checkpoint.json"
    lock_path = _lock_path_for(checkpoint_path)

    if args.reset and args.resume:
        raise SystemExit("Use either --reset (fresh grid) or --resume (continue), not both.")
    if args.reset:
        _reset_sweep_artifacts(checkpoint_path, args.output, args.output.parent)

    _acquire_lock(lock_path)

    cells_total = len(abstain_vals) * len(uncertain_vals)
    rows: list[dict[str, Any]] = []
    completed_keys: set[str] = set()
    sweep_batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.resume:
        if not checkpoint_path.is_file():
            raise SystemExit(f"--resume requires existing checkpoint at {checkpoint_path}")
        cp = _load_checkpoint(checkpoint_path)
        _validate_resume(
            cp,
            dataset=dataset,
            limit=args.limit,
            abstain_vals=abstain_vals,
            uncertain_vals=uncertain_vals,
            policy_ver=policy_ver,
        )
        sweep_batch = str(cp.get("sweep_batch_utc") or sweep_batch)
        rows = [dict(r) for r in (cp.get("rows") or [])]
        for pair in cp.get("completed_pairs") or []:
            if len(pair) >= 2:
                completed_keys.add(_cell_key(str(pair[0]), str(pair[1])))
        print(
            f"Resuming sweep batch={sweep_batch}: {len(completed_keys)}/{cells_total} cells already done → {checkpoint_path}",
            flush=True,
        )
    else:
        if checkpoint_path.is_file():
            try:
                cp0 = _load_checkpoint(checkpoint_path)
                if cp0.get("rows") and cp0.get("status") != "complete":
                    raise SystemExit(
                        f"Checkpoint {checkpoint_path} has partial rows. Use --resume to continue, "
                        "delete it, or pass a different --checkpoint path."
                    )
            except (json.JSONDecodeError, OSError):
                pass

    tmp_dir = args.output.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def write_rows_csv() -> None:
        if not rows:
            return
        rows.sort(key=lambda r: (float(r["abstain"]), float(r["uncertain"])))
        fieldnames = _row_fieldnames(rows)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    def persist_checkpoint(status: str) -> None:
        rel_ds = str(dataset.resolve().relative_to(ROOT.resolve())) if dataset.resolve().is_relative_to(ROOT.resolve()) else str(dataset)
        payload = {
            "schema_version": 1,
            "status": status,
            "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sweep_batch_utc": sweep_batch,
            "pipeline_policy_version": policy_ver,
            "dataset": rel_ds,
            "limit": args.limit,
            "abstain_grid": abstain_vals,
            "uncertain_grid": uncertain_vals,
            "cost_fp_no_task": cost_fp,
            "cost_fn_task": cost_fn,
            "output_csv": str(args.output),
            "write_freeze": str(args.write_freeze) if args.write_freeze else None,
            "cells_total": cells_total,
            "cells_completed": len(completed_keys),
            "completed_pairs": [k.split("|") for k in sorted(completed_keys)],
            "rows": rows,
        }
        _save_checkpoint(checkpoint_path, payload)

    for a in abstain_vals:
        for u in uncertain_vals:
            ck = _cell_key(a, u)
            if ck in completed_keys:
                print(f"Skip (done) abstain={a} uncertain={u}", flush=True)
                continue
            rows[:] = [
                r for r in rows
                if "abstain" not in r
                or "uncertain" not in r
                or _cell_key(str(r.get("abstain")), str(r.get("uncertain"))) != ck
            ]
            out_json = tmp_dir / f"_sweep_a{a}_u{u}.json"
            env = os.environ.copy()
            env["PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE"] = str(a)
            env["PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE"] = str(u)
            env["EVAL_RUN_ID"] = f"sweep-{sweep_batch}-a{a}-u{u}"
            env["LANGSMITH_SESSION_NAME"] = f"eval-policy-sweep-a{a}-u{u}-{sweep_batch}"
            env["EVAL_ABORT_EXIT_ZERO"] = "1"
            cmd = [
                sys.executable,
                str(ROOT / "tests" / "eval" / "run_eval.py"),
                "--method",
                "pipeline",
                "--dataset",
                str(dataset),
                "--output",
                str(out_json),
            ]
            if args.limit is not None:
                cmd.extend(["--limit", str(args.limit)])
            print(f"Running abstain={a} uncertain={u} ...", flush=True)
            try:
                subprocess.run(cmd, cwd=str(ROOT), env=env, check=True)
            except subprocess.CalledProcessError as exc:
                persist_checkpoint("partial")
                print(
                    f"Sweep cell failed (exit {exc.returncode}). Checkpoint saved to {checkpoint_path}. "
                    f"After quota reset: same command with --resume",
                    flush=True,
                )
                raise
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            overall = payload.get("overall") or {}
            abst = (overall.get("abstention") or {}).get("when_expected_empty") or {}
            mstats = payload.get("model_stats") or {}
            fb_samples = int(mstats.get("samples_using_fallback") or 0)
            rt_count = int(payload.get("runtime_error_count") or 0)
            rt_kinds = payload.get("runtime_error_kinds") or {}
            dataset_info = payload.get("dataset_info") or {}
            aborted_early = bool(payload.get("aborted_early") or (payload.get("eval_notes") or {}).get("aborted_early"))
            abort_reason = str(payload.get("abort_reason") or (payload.get("eval_notes") or {}).get("abort_reason") or "")
            total_samples = int((dataset_info.get("total_samples")) or 0) or args.limit or 0
            requested_samples = int(dataset_info.get("requested_samples") or total_samples or 0)
            contaminated, contam_reason = _classify_contamination(
                fb_samples=fb_samples,
                runtime_count=rt_count,
                runtime_kinds=rt_kinds,
                total_samples=total_samples,
            )
            if bool(mstats.get("contaminated")) and not contaminated:
                contaminated = True
                contam_reason = contam_reason or "fallback"
            if aborted_early:
                contaminated = True
                if abort_reason == "daily_quota":
                    contam_reason = "runtime_tpd"
                else:
                    contam_reason = contam_reason or "runtime_other"
            row = {
                "abstain": float(a),
                "uncertain": float(u),
                "title_f1": overall.get("title_f1", {}).get("f1", 0),
                "deadline_exact": overall.get("deadline_exact", 0),
                "fully_correct_pct": _fully_correct_pct(payload),
                "correct_abstain_empty_gt": abst.get("correct_abstain_rate"),
                "false_answer_empty_gt": abst.get("false_answer_rate"),
                "ece": (overall.get("calibration") or {}).get("ece"),
                "fallback_calls": int(mstats.get("fallback_calls") or 0),
                "samples_using_fallback": fb_samples,
                "rate_limited_calls": int(mstats.get("rate_limited_calls_total") or 0),
                "strict_primary_mode": bool(mstats.get("strict_primary_mode")),
                "runtime_error_count": rt_count,
                "runtime_error_kinds": ",".join(f"{k}={v}" for k, v in sorted(rt_kinds.items(), key=lambda x: -x[1])) if rt_kinds else "",
                "aborted_early": aborted_early,
                "abort_reason": abort_reason,
                "samples_completed": total_samples,
                "samples_requested": requested_samples,
                "contaminated": contaminated,
                "contaminated_reason": contam_reason or "",
            }
            if contaminated:
                print(
                    f"  WARNING: cell abstain={a} uncertain={u} contaminated "
                    f"(reason={contam_reason}, samples_using_fallback={fb_samples}, "
                    f"runtime_errors={rt_count}/{total_samples}, kinds={dict(rt_kinds) if rt_kinds else '-'}); "
                    "excluded from best-pick unless EVAL_SWEEP_ALLOW_CONTAMINATED=1 "
                    "(runtime-error gate: EVAL_SWEEP_RUNTIME_TOLERANCE / EVAL_SWEEP_ALLOW_RUNTIME_ERRORS).",
                    flush=True,
                )
            rows.append(row)
            if not aborted_early:
                completed_keys.add(ck)
                print(
                    f"  Kept cell eval JSON for analysis/offline replay: {out_json}",
                    flush=True,
                )
            if aborted_early and abort_reason == "daily_quota" and _stop_on_daily_quota():
                write_rows_csv()
                persist_checkpoint("blocked_quota")
                print(
                    "Stopping sweep: daily quota was exhausted inside this cell. "
                    f"Checkpoint saved to {checkpoint_path}; resume after quota reset with --resume.",
                    flush=True,
                )
                return 2
            if (
                aborted_early
                and abort_reason == "organization_restricted"
                and _stop_on_organization_restricted()
            ):
                write_rows_csv()
                persist_checkpoint("blocked_organization")
                print(
                    "Stopping sweep: Groq organization restricted inside this cell. "
                    f"Checkpoint saved to {checkpoint_path}; resolve API access, then --resume or re-run.",
                    flush=True,
                )
                return 2
            persist_checkpoint("partial" if len(completed_keys) < cells_total else "complete")

            cell_cool = float(os.getenv("EVAL_SWEEP_CELL_COOLDOWN_SECONDS", "60"))
            if cell_cool > 0 and len(completed_keys) < cells_total:
                print(f"  ... sweep cell cooldown {cell_cool}s", flush=True)
                time.sleep(cell_cool)

    if not rows:
        print("No rows to write (empty grid?).", flush=True)
        return 1

    write_rows_csv()

    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"Cost weights: FP_no_task={cost_fp} FN_task={cost_fn} — tie-break: score = title_f1 - {cost_fp}*false_answer_empty_gt")

    best = _pick_best_row(rows, cost_fp=cost_fp)
    if best:
        print(
            f"Picked (auto): abstain={best['abstain']} uncertain={best['uncertain']} "
            f"title_f1={best.get('title_f1')} false_answer_empty_gt={best.get('false_answer_empty_gt')} "
            f"fully_correct_pct={best.get('fully_correct_pct')}",
            flush=True,
        )
    elif _require_clean_candidate() and not _allow_contaminated():
        print(
            "No clean sweep cell available to pick (all rows contaminated and "
            "EVAL_SWEEP_ALLOW_CONTAMINATED=0). Keep checkpoint/CSV for triage, "
            "then resume a clean sweep after quota reset.",
            flush=True,
        )
        persist_checkpoint("complete_no_clean_candidate")
        return 2

    if len(completed_keys) == cells_total and args.write_freeze and best:
        fa_raw = best.get("false_answer_empty_gt")
        freeze_payload = {
            "status": "complete",
            "sweep_batch_utc": sweep_batch,
            "pipeline_policy_version": policy_ver,
            "dataset": str(dataset),
            "limit": args.limit,
            "cost_fp_no_task": cost_fp,
            "cost_fn_task": cost_fn,
            "scoring": "maximize title_f1 - cost_fp_no_task * false_answer_empty_gt; tie-break title_f1 then fully_correct_pct",
            "chosen": {
                "confidence_abstain_threshold": best["abstain"],
                "confidence_uncertain_threshold": best["uncertain"],
                "metrics_snapshot": best,
            },
            "csv_path": str(args.output.resolve().relative_to(ROOT.resolve()))
            if args.output.resolve().is_relative_to(ROOT.resolve())
            else str(args.output),
            "checkpoint_path": str(checkpoint_path.resolve().relative_to(ROOT.resolve()))
            if checkpoint_path.resolve().is_relative_to(ROOT.resolve())
            else str(checkpoint_path),
        }
        _write_freeze_artifact(args.write_freeze, freeze_payload)
        print(f"Wrote freeze artifact {args.write_freeze}", flush=True)
    elif args.write_freeze:
        print(
            f"Skipping --write-freeze ({len(completed_keys)}/{cells_total} cells); finish sweep then re-run or write freeze manually.",
            flush=True,
        )

    persist_checkpoint("complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
