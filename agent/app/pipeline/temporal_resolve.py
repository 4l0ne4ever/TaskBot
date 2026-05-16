"""
Deterministic calendar resolution for ``deadline_v2``.

Architecture (neuro-symbolic, v2):
- The LLM outputs ``phrase_class`` + ``phrase_params`` that encode the *semantic
  intent* of a temporal expression in any language.
- This module converts those structured intents into concrete ISO dates using
  pure deterministic arithmetic. It is completely language-agnostic: the LLM
  already normalises the phrase (e.g. "thứ Sáu tới", "next Friday", "vendredi
  prochain") into canonical ``phrase_class``/``phrase_params`` before we see it.
- If ``phrase_class`` is absent (legacy LLM output or backward-compat path),
  the old closed-set text-pattern fallback is used unchanged.

Phrase classes handled deterministically:
  named_weekday    → specific weekday name; params: {weekday, offset}
  n_days           → "in N days"; params: {n}
  tomorrow         → reference_date + 1
  today            → reference_date
  end_of_period    → end of week/month/quarter/year; params: {period}
  start_of_period  → start of week/month/quarter/year; params: {period, offset_periods}
  nth_of_month     → specific day number in a month; params: {n, month_offset}
  absolute         → date already explicit in iso field; no computation needed
  named_cultural   → Tết, Christmas, etc.; no deterministic resolution → is_ambiguous
  none             → no deadline

Two post-computation validators are applied regardless of path:
  1. Plausibility window — drops dates outside [anchor-1d, anchor+365d].
  2. (Legacy path only) Weekday consistency gate — catches arithmetic errors in
     old-style outputs that lacked phrase_class.

Research basis: neuro-symbolic temporal reasoning (TReMu, Hu et al., EMNLP 2024,
arXiv:2406.17808; NeSTR, arXiv:2512.07218).
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any

_MAX_PAST_DAYS = 1
_MAX_FUTURE_DAYS = 365

# ── Weekday helpers ────────────────────────────────────────────────────────────

# English-only: the LLM normalises weekday names from any source language.
_WEEKDAY_TO_INT: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# Legacy closed-set (backward compat for outputs without phrase_class).
_WEEKDAY_NAME_TO_INT_LEGACY: dict[str, int] = {
    "monday": 0,    "tuesday": 1,    "wednesday": 2, "thursday": 3,
    "friday": 4,    "saturday": 5,   "sunday": 6,
    "thứ hai": 0,   "thứ ba": 1,     "thứ tư": 2,    "thứ năm": 3,
    "thứ sáu": 4,   "thứ bảy": 5,    "chủ nhật": 6,
}


def _next_weekday_on_or_after(ref: date, target_weekday: int) -> date:
    delta = (target_weekday - ref.weekday()) % 7
    return ref + timedelta(days=delta)


def _end_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _end_of_quarter(d: date) -> date:
    quarter_end_month = ((d.month - 1) // 3 + 1) * 3
    return date(d.year, quarter_end_month, calendar.monthrange(d.year, quarter_end_month)[1])


def _add_months(d: date, n: int) -> date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


# ── Phrase-class handlers ──────────────────────────────────────────────────────

def _resolve_phrase_class(
    phrase_class: str,
    phrase_params: dict[str, Any] | None,
    anchor: date,
) -> date | None:
    """Return an ISO date for a recognised phrase_class, or None when the class
    either has no deterministic resolution (named_cultural, none) or the params
    are invalid.
    """
    p = phrase_params or {}

    if phrase_class == "named_weekday":
        wd_str = str(p.get("weekday") or "").lower().strip()
        wd = _WEEKDAY_TO_INT.get(wd_str)
        if wd is None:
            return None
        base = _next_weekday_on_or_after(anchor, wd)
        offset = str(p.get("offset") or "this").lower()
        if offset == "next":
            base += timedelta(days=7)
        elif offset == "after_next":
            base += timedelta(days=14)
        # "this" / "unknown" / anything else → nearest occurrence
        return base

    if phrase_class == "n_days":
        n = p.get("n")
        if not isinstance(n, int) or n < 0 or n > _MAX_FUTURE_DAYS:
            return None
        return anchor + timedelta(days=n)

    if phrase_class == "tomorrow":
        return anchor + timedelta(days=1)

    if phrase_class == "today":
        return anchor

    if phrase_class == "end_of_period":
        period = str(p.get("period") or "").lower()
        if period == "week":
            # ISO: Sunday is the last day of the week (weekday 6)
            days_to_sunday = (6 - anchor.weekday()) % 7
            return anchor + timedelta(days=days_to_sunday)
        if period == "month":
            return _end_of_month(anchor)
        if period == "quarter":
            return _end_of_quarter(anchor)
        if period == "year":
            return date(anchor.year, 12, 31)
        return None

    if phrase_class == "start_of_period":
        period = str(p.get("period") or "").lower()
        offset = int(p.get("offset_periods") or 0)
        if period == "week":
            # Monday of the target week (0 = current week, 1 = next, …)
            days_to_monday = (-anchor.weekday()) % 7
            base_monday = anchor + timedelta(days=days_to_monday)
            return base_monday + timedelta(weeks=offset)
        if period == "month":
            return _add_months(date(anchor.year, anchor.month, 1), offset)
        if period == "quarter":
            current_q_start_month = ((anchor.month - 1) // 3) * 3 + 1
            target = _add_months(date(anchor.year, current_q_start_month, 1), offset * 3)
            return target
        if period == "year":
            return date(anchor.year + offset, 1, 1)
        return None

    if phrase_class == "nth_of_month":
        n = p.get("n")
        if not isinstance(n, int) or n < 1 or n > 31:
            return None
        month_offset = int(p.get("month_offset") or 0)
        try:
            candidate = date(anchor.year, anchor.month, n)
        except ValueError:
            candidate = None
        if candidate is None or month_offset == 1 or candidate < anchor:
            next_month = _add_months(date(anchor.year, anchor.month, 1), 1)
            max_day = calendar.monthrange(next_month.year, next_month.month)[1]
            try:
                candidate = date(next_month.year, next_month.month, min(n, max_day))
            except ValueError:
                return None
        return candidate

    # absolute → iso is already set by LLM; named_cultural / none → no resolution
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_anchor_date(sent_at: str | None) -> date | None:
    if not sent_at or not isinstance(sent_at, str):
        return None
    try:
        return date.fromisoformat(sent_at.strip()[:10])
    except ValueError:
        return None


def _is_plausible(iso_value: str, anchor: date) -> bool:
    try:
        d = date.fromisoformat(iso_value)
    except ValueError:
        return False
    delta = (d - anchor).days
    return -_MAX_PAST_DAYS <= delta <= _MAX_FUTURE_DAYS


# ── Legacy closed-set (backward compat) ───────────────────────────────────────

def try_resolve_deadline_iso(deadline_v2: dict[str, Any], anchor: date) -> str | None:
    """Legacy resolver: closed-set text-pattern detection for outputs without phrase_class."""
    raw_text = deadline_v2.get("text") or deadline_v2.get("resolved_from") or ""
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    text = raw_text.strip()
    low = text.lower()

    # "in N days" / "trong N ngày"
    m = re.search(r"(\d+)\s*(?:ngày|days?)\b", low, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 0 <= n <= _MAX_FUTURE_DAYS:
            return (anchor + timedelta(days=n)).isoformat()

    # "tomorrow" / "ngày mai"
    if re.search(r"\b(?:tomorrow|ngày\s+mai)\b", low, flags=re.IGNORECASE):
        return (anchor + timedelta(days=1)).isoformat()

    # Closed-set weekday names (EN + VI)
    for name, wd in _WEEKDAY_NAME_TO_INT_LEGACY.items():
        if name in low:
            return _next_weekday_on_or_after(anchor, wd).isoformat()

    return None


def _detect_weekday_in_text_legacy(low: str) -> int | None:
    for name, wd in _WEEKDAY_NAME_TO_INT_LEGACY.items():
        if name in low:
            return wd
    return None


def _apply_week_offset(base: date, week_offset: str | None) -> date:
    if week_offset == "next":
        return base + timedelta(days=7)
    if week_offset == "after_next":
        return base + timedelta(days=14)
    return base


# ── Main enrichment function ───────────────────────────────────────────────────

def enrich_deadline_v2_with_symbolic_iso(
    deadline_v2: dict[str, Any],
    anchor: date | None,
) -> dict[str, Any]:
    """Apply deterministic resolution and arithmetic guards to ``deadline_v2``.

    Priority order:
    1. If ``phrase_class`` is present → use the phrase-class handler (v2 path).
    2. Otherwise → legacy closed-set text-pattern fallback (v1 path).
    In both cases, plausibility validation is applied afterward.
    """
    out = dict(deadline_v2)

    if not anchor:
        return out

    phrase_class = out.get("phrase_class")
    existing_iso = out.get("iso") if isinstance(out.get("iso"), str) else None

    # ── Plausibility gate on any existing iso (both paths) ────────────────────
    if existing_iso and not _is_plausible(existing_iso, anchor):
        out["iso"] = None
        if out.get("type") == "exact":
            out["type"] = "relative"
        existing_iso = None

    # ── V2 path: phrase_class present ─────────────────────────────────────────
    if phrase_class and phrase_class not in ("absolute", "named_cultural", "none"):
        params = out.get("phrase_params") or {}
        computed = _resolve_phrase_class(phrase_class, params, anchor)
        if computed and _is_plausible(computed.isoformat(), anchor):
            out["iso"] = computed.isoformat()
            if out.get("type") in (None, "none", "exact"):
                out["type"] = "relative"
            return out
        # V2 resolution yielded nothing (phrase_params invalid or missing) —
        # fall through to V1 text-pattern rescue rather than returning None.

    if phrase_class in ("named_cultural", "none"):
        out["is_ambiguous"] = True
        return out

    # ── V1 fallback path: legacy text-pattern + weekday gate ─────────────────
    # When week_offset is null (new prompt style), check phrase_params.offset
    # as a cross-path hint so that weekday offset intent is not lost even when
    # V2 phrase_class resolution failed due to bad/missing phrase_params.weekday.
    week_offset = out.get("week_offset")
    if not week_offset:
        pp_offset = str((out.get("phrase_params") or {}).get("offset") or "").lower()
        if pp_offset in ("next", "after_next"):
            week_offset = pp_offset
    low = (out.get("text") or out.get("resolved_from") or "").lower()

    if existing_iso:
        # Non-weekday closed-set gate: correct arithmetic errors
        symbolic = try_resolve_deadline_iso(out, anchor)
        has_weekday = _detect_weekday_in_text_legacy(low) is not None
        if symbolic and symbolic != existing_iso and not has_weekday:
            out["iso"] = symbolic
            if out.get("type") == "exact":
                out["type"] = "relative"
            existing_iso = symbolic

        # Weekday consistency gate
        expected_wd = _detect_weekday_in_text_legacy(low)
        if expected_wd is not None:
            if week_offset in ("next", "after_next"):
                base = _next_weekday_on_or_after(anchor, expected_wd)
                corrected = _apply_week_offset(base, week_offset).isoformat()
                if _is_plausible(corrected, anchor):
                    out["iso"] = corrected
                    if out.get("type") == "exact":
                        out["type"] = "relative"
                    existing_iso = corrected
            else:
                actual_wd = date.fromisoformat(existing_iso).weekday() if existing_iso else None
                if actual_wd is not None and actual_wd != expected_wd:
                    corrected = _next_weekday_on_or_after(anchor, expected_wd).isoformat()
                    if _is_plausible(corrected, anchor):
                        out["iso"] = corrected
                        if out.get("type") == "exact":
                            out["type"] = "relative"

        return out

    # iso missing in v1 path — try closed-set resolver
    candidate = try_resolve_deadline_iso(out, anchor)
    if not candidate:
        return out
    expected_wd = _detect_weekday_in_text_legacy(low)
    if expected_wd is not None and week_offset in ("next", "after_next"):
        base = _next_weekday_on_or_after(anchor, expected_wd)
        candidate = _apply_week_offset(base, week_offset).isoformat()
    if _is_plausible(candidate, anchor):
        out["iso"] = candidate
        if out.get("type") in (None, "none", "relative"):
            out["type"] = "relative"

    return out
