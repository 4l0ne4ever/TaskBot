from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


@dataclass(frozen=True)
class PipelinePolicy:
    version: str
    confidence_abstain_threshold: float
    confidence_uncertain_threshold: float
    conflict_title_similarity_threshold: float
    multi_source_title_similarity_threshold: float
    multi_source_conflict_lookback_days: int
    max_conflict_checks_per_task: int
    extraction_guidance: str
    validate_evidence_in_source: bool


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _policy_bundle_path() -> Path:
    return Path(__file__).resolve().parent / "policies" / "policies.yaml"


@lru_cache(maxsize=64)
def _load_pipeline_policy(
    version_key: str,
    abstain_override: str | None,
    uncertain_override: str | None,
) -> PipelinePolicy:
    settings = get_settings()
    data: dict[str, Any] = {}
    bundle = _policy_bundle_path()
    if bundle.is_file():
        with bundle.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            block = raw.get(version_key)
            if isinstance(block, dict):
                data = block
    eg = data.get("extraction_guidance")
    extraction_guidance = eg.strip() if isinstance(eg, str) else ""

    abstain = _coerce_float(
        data.get("confidence_abstain_threshold"),
        settings.confidence_abstain_threshold,
    )
    uncertain = _coerce_float(
        data.get("confidence_uncertain_threshold"),
        settings.confidence_uncertain_threshold,
    )
    if abstain_override:
        abstain = float(abstain_override)
    if uncertain_override:
        uncertain = float(uncertain_override)

    ve_src = data.get("validate_evidence_in_source")
    if isinstance(ve_src, bool):
        validate_evidence_in_source = ve_src
    else:
        validate_evidence_in_source = str(ve_src or "true").lower() in {"1", "true", "yes"}

    max_conflict_checks = _coerce_int(
        data.get("max_conflict_checks_per_task"),
        settings.max_conflict_checks_per_task,
    )
    conflict_checks_override = os.getenv("PIPELINE_POLICY_MAX_CONFLICT_CHECKS_OVERRIDE")
    if conflict_checks_override is None:
        eval_conflict = os.getenv("EVAL_ENABLE_CONFLICT_CHECK")
        if eval_conflict is not None and not _coerce_bool(eval_conflict, True):
            conflict_checks_override = "0"
    if conflict_checks_override is not None:
        max_conflict_checks = max(0, _coerce_int(conflict_checks_override, max_conflict_checks))

    return PipelinePolicy(
        version=str(data.get("version") or f"policy_{version_key}"),
        confidence_abstain_threshold=abstain,
        confidence_uncertain_threshold=uncertain,
        conflict_title_similarity_threshold=_coerce_float(
            data.get("conflict_title_similarity_threshold"),
            settings.conflict_title_similarity_threshold,
        ),
        multi_source_title_similarity_threshold=_coerce_float(
            data.get("multi_source_title_similarity_threshold"),
            settings.multi_source_title_similarity_threshold,
        ),
        multi_source_conflict_lookback_days=_coerce_int(
            data.get("multi_source_conflict_lookback_days"),
            settings.multi_source_conflict_lookback_days,
        ),
        max_conflict_checks_per_task=max_conflict_checks,
        extraction_guidance=extraction_guidance,
        validate_evidence_in_source=validate_evidence_in_source,
    )


def get_pipeline_policy() -> PipelinePolicy:
    settings = get_settings()
    key = (settings.pipeline_policy_version or "v1").strip().lower()
    if key.startswith("policy_"):
        key = key[7:]
    return _load_pipeline_policy(
        key,
        os.getenv("PIPELINE_POLICY_CONFIDENCE_ABSTAIN_OVERRIDE"),
        os.getenv("PIPELINE_POLICY_CONFIDENCE_UNCERTAIN_OVERRIDE"),
    )
