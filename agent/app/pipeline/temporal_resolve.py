"""
Deterministic calendar resolution and arithmetic guard for ``deadline_v2``.

Design choice (Q-01, see docs/quality-issues-tracker.md):
- The LLM is the primary resolver; it outputs a structured ``deadline_v2`` with
  ``type``, ``text``, and a candidate ``iso`` when it can compute one.
- This module is intentionally a **small closed-set symbolic fallback** for a
  few language-intrinsic phrase classes (``in N days``, weekday names,
  tomorrow / ngày mai). Anything outside this set is left unresolved so the
  downstream pipeline can abstain or lower confidence, rather than widening the
  regex surface for open-ended phrases like "end of week" / "hết quý".
- After resolution we run two validators against the anchor date:
  1. A plausibility window — iso values far outside ``[anchor - past,
     anchor + future]`` are dropped.
  2. A **weekday consistency gate** — when the phrase names a weekday from
     our closed set, the iso produced by the LLM must actually fall on that
     weekday; otherwise we override it with the deterministic symbolic
     resolution. This catches a systematic +1-day LLM arithmetic error
     observed on ~40% of Friday/"thứ Sáu" samples in the clean
     eval batch, without extending the closed phrase set.

This is not enumeration: the closed set of weekday phrases and the
``in N days`` / tomorrow classes is deliberately small and bounded. The
gate only validates arithmetic on phrases **already in** that set; it does
not resolve new ones. Research basis: neuro-symbolic temporal reasoning
(TReMu, Hu et al., EMNLP 2024, arXiv:2406.17808) treats LLM output as a
proposal and uses a deterministic layer to reject arithmetically
inconsistent candidates.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

_MAX_PAST_DAYS = 1
_MAX_FUTURE_DAYS = 365

_WEEKDAY_NAME_TO_INT: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "thứ hai": 0,
    "thứ ba": 1,
    "thứ tư": 2,
    "thứ năm": 3,
    "thứ sáu": 4,
    "thứ bảy": 5,
    "chủ nhật": 6,
}


def parse_anchor_date(sent_at: str | None) -> date | None:
    if not sent_at or not isinstance(sent_at, str):
        return None
    part = sent_at.strip()[:10]
    try:
        return date.fromisoformat(part)
    except ValueError:
        return None


def _next_weekday_on_or_after(ref: date, target_weekday: int) -> date:
    delta = (target_weekday - ref.weekday()) % 7
    return ref + timedelta(days=delta)


def _detect_weekday_in_text(low: str) -> int | None:
    for name, w in _WEEKDAY_NAME_TO_INT.items():
        if name in low:
            return w
    return None


def _try_in_n_days(text: str, anchor: date) -> date | None:
    m = re.search(r"(\d+)\s*(?:ngày|days?)\b", text, flags=re.IGNORECASE)
    if not m:
        return None
    n = int(m.group(1))
    if n < 0 or n > _MAX_FUTURE_DAYS:
        return None
    return anchor + timedelta(days=n)


def _try_tomorrow(text: str, anchor: date) -> date | None:
    if re.search(r"\b(?:tomorrow|ngày\s+mai)\b", text, flags=re.IGNORECASE):
        return anchor + timedelta(days=1)
    return None


def _is_plausible(iso_value: str, anchor: date) -> bool:
    try:
        d = date.fromisoformat(iso_value)
    except ValueError:
        return False
    delta_days = (d - anchor).days
    return -_MAX_PAST_DAYS <= delta_days <= _MAX_FUTURE_DAYS


def try_resolve_deadline_iso(deadline_v2: dict[str, Any], anchor: date) -> str | None:
    """Return YYYY-MM-DD if phrase + anchor yield a single day in the closed set, else None."""
    raw_text = deadline_v2.get("text") or deadline_v2.get("resolved_from") or ""
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    text = raw_text.strip()
    low = text.lower()

    if d := _try_in_n_days(low, anchor):
        return d.isoformat()

    if d := _try_tomorrow(text, anchor):
        return d.isoformat()

    wd = _detect_weekday_in_text(low)
    if wd is not None:
        return _next_weekday_on_or_after(anchor, wd).isoformat()

    return None


def _iso_weekday(iso_value: str) -> int | None:
    try:
        return date.fromisoformat(iso_value).weekday()
    except ValueError:
        return None


def _expected_weekday_from_phrase(deadline_v2: dict[str, Any]) -> int | None:
    """Return the weekday index demanded by the phrase, if any closed-set name is present.

    We only consider the weekday names already in ``_WEEKDAY_NAME_TO_INT``. When
    neither Vietnamese "thứ …" nor English weekday is present, we return ``None``
    and the gate becomes a no-op.
    """
    raw = deadline_v2.get("text") or deadline_v2.get("resolved_from") or ""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _detect_weekday_in_text(raw.lower())


def _has_weekday_phrase(deadline_v2: dict[str, Any]) -> bool:
    return _expected_weekday_from_phrase(deadline_v2) is not None


def enrich_deadline_v2_with_symbolic_iso(deadline_v2: dict[str, Any], anchor: date | None) -> dict[str, Any]:
    """Return a copy of ``deadline_v2`` with arithmetic guards applied.

    Behaviour:

    - Missing iso + anchor: try the closed-set resolver; if it returns a
      plausible date we record it with ``type=relative``. If it does not match
      the closed set, iso stays empty (the pipeline will then abstain or rely
      on LLM signals).
    - Existing iso: validate against the anchor window; values far outside are
      dropped so obvious LLM arithmetic errors are not persisted as truth.
    - Existing iso + phrase with a closed-set weekday: if the iso does not
      land on that weekday, override with the symbolic next-occurrence. This
      is the arithmetic guard, not enumeration — we already have the weekday
      in the closed set, we are only checking the date produced for it.
    """
    out = dict(deadline_v2)
    existing_iso = out.get("iso") if isinstance(out.get("iso"), str) else None
    if existing_iso and anchor and not _is_plausible(existing_iso, anchor):
        out["iso"] = None
        if out.get("type") == "exact":
            out["type"] = "relative"
        existing_iso = None

    if existing_iso and anchor:
        # For closed-set non-weekday phrases (e.g. tomorrow / in N days),
        # any concrete ISO disagreement is arithmetic error, not language
        # ambiguity. Weekday phrases keep the narrower weekday gate below so
        # language-level current/next modifiers remain model-driven.
        symbolic = try_resolve_deadline_iso(out, anchor)
        if symbolic and symbolic != existing_iso and not _has_weekday_phrase(out):
            out["iso"] = symbolic
            if out.get("type") == "exact":
                out["type"] = "relative"
            existing_iso = symbolic
        expected_wd = _expected_weekday_from_phrase(out)
        if expected_wd is not None:
            actual_wd = _iso_weekday(existing_iso)
            if actual_wd is not None and actual_wd != expected_wd:
                corrected = _next_weekday_on_or_after(anchor, expected_wd).isoformat()
                if _is_plausible(corrected, anchor):
                    out["iso"] = corrected
                    if out.get("type") == "exact":
                        out["type"] = "relative"
                    existing_iso = corrected

    if out.get("iso") or not anchor:
        return out
    candidate = try_resolve_deadline_iso(out, anchor)
    if not candidate or not _is_plausible(candidate, anchor):
        return out
    out["iso"] = candidate
    if out.get("type") in (None, "none", "relative"):
        out["type"] = "relative"
    return out
