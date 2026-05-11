"""Post-hoc confidence calibration for the validation node (Q-04).

Loads a versioned calibration artifact produced by
``tests/eval/fit_verbalized_calibration.py`` and exposes a ``Calibrator``
that remaps raw verbalized confidence to a calibrated score *before* the
policy thresholds are evaluated.

Why remap before policy:
    Policy thresholds are specified on the calibrated scale. If calibration
    happened *after* banding, changing the calibrator would silently move
    the effective decision boundary — the opposite of the versioned,
    reproducible contract we want. Applying calibration first keeps the
    thresholds stable across fits (Guo et al. 2017 "On Calibration of Modern
    Neural Networks"; Platt 1999; Zadrozny & Elkan 2001).

Two artifact shapes are supported — matching the two ``fit_*`` methods:

* ``isotonic``: a list of ``[x, y]`` knots; applied with linear
  interpolation between knots and clamping at the endpoints.
* ``histogram_binning``: equal-width bins with ``empirical_accuracy``;
  applied by bin lookup. Empty bins hold a ``0.5`` Laplace prior so the
  mapping stays defined on the full ``[0,1]`` range.

If ``CALIBRATION_ARTIFACT_PATH`` is unset or the artifact is missing /
unreadable / uses an unknown method, we return ``None`` so callers fall
back to identity (raw confidence passes through unchanged). This is the
safe default — we never want a missing file to silently shift the policy.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_METHODS = frozenset({"isotonic", "histogram_binning"})


@dataclass(frozen=True)
class Calibrator:
    """Callable calibration model with provenance.

    ``method`` + ``source`` identify which artifact was loaded so the
    pipeline can emit ``calibration_version`` on every task it touches.
    Applying the calibrator is pure / stateless, so a ``Calibrator``
    instance can be cached across pipeline invocations safely.
    """

    method: str
    source: str
    artifact_schema_version: int
    fit_time_utc: str | None
    git_sha: str | None
    source_eval_sha256: str | None
    pairs_used: int
    ece_before: float | None
    ece_after: float | None
    knots: tuple[tuple[float, float], ...] = ()
    bins: tuple[tuple[float, float, float], ...] = ()  # (lo, hi, empirical_accuracy)

    def apply(self, x: float) -> float:
        try:
            raw = float(x)
        except (TypeError, ValueError):
            return float("nan")
        raw = max(0.0, min(1.0, raw))
        if self.method == "isotonic":
            return _apply_isotonic(self.knots, raw)
        if self.method == "histogram_binning":
            return _apply_histogram(self.bins, raw)
        return raw

    def version_tag(self) -> str:
        """Short identifier used for audit logs & task fields."""
        short_sha = (self.git_sha or "nogit")[:8]
        return f"{self.method}@{short_sha}:{self.fit_time_utc or 'unknown'}"


def _apply_isotonic(knots: tuple[tuple[float, float], ...], x: float) -> float:
    if not knots:
        return x
    if x <= knots[0][0]:
        return knots[0][1]
    if x >= knots[-1][0]:
        return knots[-1][1]
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
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _apply_histogram(bins: tuple[tuple[float, float, float], ...], x: float) -> float:
    if not bins:
        return x
    for lo, hi, ea in bins:
        if lo <= x < hi:
            return ea
    return bins[-1][2]


def _from_payload(payload: dict, source: str) -> Calibrator | None:
    method = str(payload.get("method") or "").strip()
    if method not in SUPPORTED_METHODS:
        logger.warning(
            "calibration artifact %s has unsupported method=%r; falling back to identity",
            source,
            method,
        )
        return None

    knots: tuple[tuple[float, float], ...] = ()
    bins: tuple[tuple[float, float, float], ...] = ()
    if method == "isotonic":
        raw_knots = payload.get("knots") or []
        parsed: list[tuple[float, float]] = []
        for pair in raw_knots:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            try:
                parsed.append((float(pair[0]), float(pair[1])))
            except (TypeError, ValueError):
                continue
        if not parsed:
            logger.warning("calibration artifact %s has empty/invalid isotonic knots", source)
            return None
        knots = tuple(parsed)
    else:
        raw_bins = payload.get("bins") or []
        parsed_bins: list[tuple[float, float, float]] = []
        for b in raw_bins:
            if not isinstance(b, dict):
                continue
            try:
                lo = float(b["lo"])
                hi = float(b["hi"])
                ea = b.get("empirical_accuracy")
                if ea is None:
                    continue
                parsed_bins.append((lo, hi, float(ea)))
            except (TypeError, ValueError, KeyError):
                continue
        if not parsed_bins:
            logger.warning("calibration artifact %s has empty/invalid histogram bins", source)
            return None
        bins = tuple(parsed_bins)

    pairs_used = int(payload.get("pairs_used") or 0)
    try:
        schema = int(payload.get("artifact_schema_version") or 0)
    except (TypeError, ValueError):
        schema = 0

    return Calibrator(
        method=method,
        source=source,
        artifact_schema_version=schema,
        fit_time_utc=str(payload.get("fit_time_utc") or "") or None,
        git_sha=str(payload.get("git_sha") or "") or None,
        source_eval_sha256=str(payload.get("source_eval_sha256") or "") or None,
        pairs_used=pairs_used,
        ece_before=_maybe_float(payload.get("ece_before")),
        ece_after=_maybe_float(payload.get("ece_after")),
        knots=knots,
        bins=bins,
    )


def _maybe_float(v: object) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _load_from_path(path: Path) -> Calibrator | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("calibration artifact %s unreadable: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        logger.warning("calibration artifact %s is not a JSON object", path)
        return None
    return _from_payload(payload, str(path))


@lru_cache(maxsize=4)
def _cached_calibrator(path_str: str) -> Calibrator | None:
    path = Path(path_str)
    if not path.is_file():
        logger.info("calibration artifact not found at %s; using identity", path)
        return None
    return _load_from_path(path)


def _env_artifact_path() -> str | None:
    """Resolve the artifact path, preferring the live env var so tests can
    flip calibration on/off without touching the pydantic settings cache.

    Falls back to ``settings.calibration_artifact_path`` (loaded from
    ``.env``) so production deployments can configure the path once in the
    environment file without exporting it in shells.
    """
    val = os.getenv("CALIBRATION_ARTIFACT_PATH")
    if val and val.strip():
        return val.strip()
    try:
        from app.config import get_settings

        cfg_val = get_settings().calibration_artifact_path
    except Exception:  # settings unavailable (import-time in tests): ignore
        return None
    if cfg_val and str(cfg_val).strip():
        return str(cfg_val).strip()
    return None

def get_runtime_calibrator() -> Calibrator | None:
    """Return the active calibrator, or ``None`` when disabled.

    The artifact path is resolved from the ``CALIBRATION_ARTIFACT_PATH``
    environment variable every call (so tests / eval runs can swap the
    artifact without restarting the process), but parsed payloads are
    cached per path.
    """
    path = _env_artifact_path()
    if not path:
        
        return None
    return _cached_calibrator(path)


def reset_calibrator_cache() -> None:
    """Drop the parsed-artifact cache. Intended for tests and for ops reloads
    after writing a new artifact at the same path.
    """
    _cached_calibrator.cache_clear()
