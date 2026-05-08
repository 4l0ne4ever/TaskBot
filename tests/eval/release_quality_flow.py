#!/usr/bin/env python3
"""Orchestrate release-quality eval flow with frozen policy artifact.

Flow (product-safe defaults):
  1) Optional baseline eval (`run_eval.py`) for before/after comparison.
  2) Policy sweep:
     - default: quota-safe offline sweep (`sweep_policy_thresholds_offline.py`)
       from one saved pipeline eval artifact.
     - optional: online sweep (`sweep_policy_thresholds.py`) with checkpoint/resume.
  3) Load chosen thresholds from freeze artifact.
  4) Aligned eval at frozen thresholds.
  5) Quality gate (`quality_gate.py --freeze-artifact`) on aligned eval.

This script is intentionally strict: any non-zero subprocess exit fails fast.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _cmd_to_text(cmd: Iterable[str]) -> str:
    return " ".join(cmd)


def _run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
    print(f"$ {_cmd_to_text(cmd)}", flush=True)
    if dry_run:
        return 0
    cp = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False)
    return cp.returncode


def _pipeline_eval_cmd(*, dataset: Path, output: Path, limit: int | None) -> list[str]:
    cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "run_eval.py"),
        "--method",
        "pipeline",
        "--dataset",
        str(dataset),
        "--output",
        str(output),
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    return cmd


def _load_freeze_thresholds(path: Path) -> tuple[float, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chosen = payload.get("chosen") or {}
    abstain = chosen.get("confidence_abstain_threshold")
    uncertain = chosen.get("confidence_uncertain_threshold")
    if abstain is None or uncertain is None:
        raise SystemExit(
            f"freeze artifact missing chosen thresholds: {path}"
        )
    return float(abstain), float(uncertain)


def _normalize_policy_version(value: str) -> str:
    txt = str(value or "").strip().lower()
    if txt.startswith("policy_"):
        txt = txt[7:]
    return txt


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_policy_keys() -> set[str]:
    policy_bundle = ROOT / "agent" / "app" / "pipeline" / "policies" / "policies.yaml"
    payload = yaml.safe_load(policy_bundle.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return set()
    return {str(k).strip().lower() for k in payload.keys()}


def _preflight_checks(*, dataset: Path, policy_version: str, env: dict[str, str]) -> list[str]:
    issues: list[str] = []
    if not dataset.is_file():
        issues.append(f"dataset not found: {dataset}")

    normalized_policy = _normalize_policy_version(policy_version)
    known_policies = _load_policy_keys()
    if normalized_policy not in known_policies:
        issues.append(
            f"unknown policy version '{policy_version}' (normalized='{normalized_policy}', available={sorted(known_policies)})"
        )

    required_env = ("GROQ_API_KEY", "DATABASE_URL")
    for key in required_env:
        if not str(env.get(key) or "").strip():
            issues.append(f"missing required env: {key}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release-quality eval/sweep/gate pipeline")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "tests" / "eval" / "labeled_dataset.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--policy-version",
        type=str,
        default=(os.getenv("PIPELINE_POLICY_VERSION") or "v1"),
        help="Policy preset key (v1/v2/v3) used for sweep/eval",
    )
    parser.add_argument(
        "--baseline-output",
        type=Path,
        default=ROOT / "tests" / "eval" / "results" / "pipeline_baseline.json",
    )
    parser.add_argument(
        "--aligned-output",
        type=Path,
        default=ROOT / "tests" / "eval" / "results" / "pipeline_frozen_eval.json",
    )
    parser.add_argument(
        "--sweep-output",
        type=Path,
        default=ROOT / "tests" / "eval" / "policy_freeze" / "sweep_release.csv",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / "tests" / "eval" / "policy_freeze" / "sweep_release_checkpoint.json",
    )
    parser.add_argument(
        "--freeze-artifact",
        type=Path,
        default=ROOT / "tests" / "eval" / "policy_freeze" / "chosen_release.json",
    )
    parser.add_argument(
        "--sweep-mode",
        type=str,
        choices=("offline", "online"),
        default=(os.getenv("EVAL_SWEEP_MODE") or "offline").strip().lower(),
        help=(
            "Threshold-sweep mode: offline (default, quota-safe; recompute grid from one "
            "saved eval JSON) or online (run full grid with Groq calls per cell)."
        ),
    )
    parser.add_argument(
        "--sweep-source-result",
        type=Path,
        default=None,
        help=(
            "Offline sweep only: existing pipeline eval JSON used as source for "
            "candidate_tasks. If omitted, baseline output is reused; when "
            "--skip-baseline is set, release flow creates one source eval first."
        ),
    )
    parser.add_argument("--resume-sweep", action="store_true")
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip pre-sweep baseline run_eval",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands/env-dependent decisions without running subprocesses",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip local release preflight checks",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run release preflight checks and exit without eval/sweep",
    )
    args = parser.parse_args()

    dataset = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    baseline_output = (
        args.baseline_output if args.baseline_output.is_absolute() else ROOT / args.baseline_output
    )
    aligned_output = (
        args.aligned_output if args.aligned_output.is_absolute() else ROOT / args.aligned_output
    )
    sweep_output = (
        args.sweep_output if args.sweep_output.is_absolute() else ROOT / args.sweep_output
    )
    checkpoint = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    freeze_artifact = (
        args.freeze_artifact if args.freeze_artifact.is_absolute() else ROOT / args.freeze_artifact
    )
    for p in [baseline_output, aligned_output, sweep_output, checkpoint, freeze_artifact]:
        p.parent.mkdir(parents=True, exist_ok=True)

    base_env = os.environ.copy()
    base_env["PIPELINE_POLICY_VERSION"] = str(args.policy_version).strip()
    if _env_flag("EVAL_RELEASE_SKIP_PREFLIGHT", False):
        args.skip_preflight = True
    if not args.skip_preflight:
        issues = _preflight_checks(
            dataset=dataset,
            policy_version=args.policy_version,
            env=base_env,
        )
        if issues:
            for item in issues:
                print(f"preflight: {item}", flush=True)
            return 2
        print("preflight: OK", flush=True)
    if args.preflight_only:
        return 0

    if not args.skip_baseline:
        cmd = _pipeline_eval_cmd(dataset=dataset, output=baseline_output, limit=args.limit)
        rc = _run(cmd, env=base_env, dry_run=args.dry_run)
        if rc != 0:
            return rc

    if args.sweep_mode == "online":
        sweep_cmd = [
            sys.executable,
            str(ROOT / "tests" / "eval" / "sweep_policy_thresholds.py"),
            "--dataset",
            str(dataset),
            "--output",
            str(sweep_output),
            "--checkpoint",
            str(checkpoint),
            "--write-freeze",
            str(freeze_artifact),
        ]
        if args.limit is not None:
            sweep_cmd.extend(["--limit", str(args.limit)])
        if args.resume_sweep:
            sweep_cmd.append("--resume")
        rc = _run(sweep_cmd, env=base_env, dry_run=args.dry_run)
        if rc != 0:
            return rc
    else:
        if args.resume_sweep:
            print("note: --resume-sweep is ignored in offline mode (single-pass recomputation).", flush=True)

        source_result = (
            args.sweep_source_result
            if args.sweep_source_result is not None and args.sweep_source_result.is_absolute()
            else (ROOT / args.sweep_source_result) if args.sweep_source_result is not None else None
        )
        if source_result is None:
            if not args.skip_baseline:
                source_result = baseline_output
            else:
                source_result = sweep_output.with_name(f"{sweep_output.stem}_source_eval.json")
                source_eval_cmd = _pipeline_eval_cmd(dataset=dataset, output=source_result, limit=args.limit)
                rc = _run(source_eval_cmd, env=base_env, dry_run=args.dry_run)
                if rc != 0:
                    return rc

        offline_cmd = [
            sys.executable,
            str(ROOT / "tests" / "eval" / "sweep_policy_thresholds_offline.py"),
            "--result",
            str(source_result),
            "--output",
            str(sweep_output),
            "--write-freeze",
            str(freeze_artifact),
            "--write-aligned-result",
            str(aligned_output),
        ]
        rc = _run(offline_cmd, env=base_env, dry_run=args.dry_run)
        if rc != 0:
            return rc

    if args.dry_run:
        print("dry-run: skipping freeze parsing and aligned eval/gate execution.", flush=True)
        return 0

    abstain, uncertain = _load_freeze_thresholds(freeze_artifact)
    freeze_validate_cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "validate_freeze_artifact.py"),
        "--freeze-artifact",
        str(freeze_artifact),
    ]
    rc = _run(freeze_validate_cmd, env=base_env, dry_run=False)
    if rc != 0:
        return rc
    aligned_env = base_env.copy()
    aligned_env["PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE"] = str(abstain)
    aligned_env["PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE"] = str(uncertain)

    if args.sweep_mode == "online":
        aligned_cmd = [
            sys.executable,
            str(ROOT / "tests" / "eval" / "run_eval.py"),
            "--method",
            "pipeline",
            "--dataset",
            str(dataset),
            "--output",
            str(aligned_output),
        ]
        if args.limit is not None:
            aligned_cmd.extend(["--limit", str(args.limit)])
        rc = _run(aligned_cmd, env=aligned_env, dry_run=False)
        if rc != 0:
            return rc
    else:
        print(
            f"offline mode: using recomputed aligned eval result {aligned_output}",
            flush=True,
        )

    freeze_validate_with_eval_cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "validate_freeze_artifact.py"),
        "--freeze-artifact",
        str(freeze_artifact),
        "--eval-result",
        str(aligned_output),
    ]
    rc = _run(freeze_validate_with_eval_cmd, env=aligned_env, dry_run=False)
    if rc != 0:
        return rc

    gate_cmd = [
        sys.executable,
        str(ROOT / "tests" / "eval" / "quality_gate.py"),
        "--result",
        str(aligned_output),
        "--freeze-artifact",
        str(freeze_artifact),
    ]
    rc = _run(gate_cmd, env=aligned_env, dry_run=False)
    if rc != 0:
        return rc

    print("Release-quality flow PASSED (sweep -> aligned eval -> quality gate).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
