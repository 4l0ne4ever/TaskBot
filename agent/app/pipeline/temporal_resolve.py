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

# ── Future-week qualifier detection ────────────────────────────────────────────
#
# When the LLM emits ``phrase_class="named_weekday"`` from a phrase like
# "next Friday" / "thứ Sáu tới" / "vendredi prochain", it should also emit
# ``phrase_params.offset="next"``. Empirically the model often defaults to
# ``"this"`` (or omits the field) even when the source text carries an
# unambiguous future-week marker, which shifts the resolved date by exactly
# one week. The patterns below let us correct that deterministically by
# inspecting ``deadline_v2.text`` (verbatim from the source) instead of asking
# the LLM a second time — language-agnostic, no extra LLM call.
#
# Conservative contract:
#   - Only ever UPGRADE offset ("this"/"unknown"/missing → "next"/"after_next").
#   - Never downgrade an explicit "next" the LLM emitted.
#   - Apply only when phrase_class == "named_weekday" so generic uses of
#     "next" (e.g. "next time") in non-weekday phrases are ignored.

_AFTER_NEXT_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English: "the Friday after next"
    re.compile(r"\bafter\s+next\b", re.IGNORECASE),
    # Vietnamese: "thứ Sáu sau nữa" (the Friday two weeks out)
    re.compile(r"\bsau\s+nữa\b", re.IGNORECASE),
    # Japanese: 再来週 (the week after next)
    re.compile(r"再来週"),
    # Chinese: 下下周 / 下下星期
    re.compile(r"下\s*下\s*(?:周|週|星期)"),
)

_NEXT_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English: "next Friday" — bare "next" before/after the weekday
    re.compile(r"\bnext\b", re.IGNORECASE),
    # Vietnamese: "thứ Sáu tới" (coming Friday) / "tuần sau" (next week) /
    # "tuần tới" (coming week). "tới" alone is acceptable here because the
    # caller restricts this detector to named_weekday phrases.
    re.compile(r"\btới\b", re.IGNORECASE),
    re.compile(r"\btuần\s+(?:sau|tới)\b", re.IGNORECASE),
    # French: "vendredi prochain" / "prochaine"
    re.compile(r"\bprochain(?:e)?\b", re.IGNORECASE),
    # Spanish / Portuguese: "próximo viernes" / "próxima sexta-feira"
    re.compile(r"\bpr[oó]xim[oa]\b", re.IGNORECASE),
    # German: "nächsten Freitag" / "naechsten" (ASCII fallback)
    re.compile(r"\bn(?:ä|ae)chst(?:en|er|e|es)?\b", re.IGNORECASE),
    # Italian: "prossimo venerdì"
    re.compile(r"\bprossim[oa]\b", re.IGNORECASE),
    # Japanese: 来週 (next week)
    re.compile(r"来週"),
    # Korean: 다음 주 / 다음주
    re.compile(r"다음\s*주"),
    # Chinese: 下周 / 下星期 (next week) — guard against 下下周 by requiring
    # NOT preceded by another 下 (handled in caller via after-next first).
    re.compile(r"下\s*(?:周|週|星期)"),
)


def _detect_text_offset(text: str | None) -> str | None:
    """Return "after_next", "next", or None based on next-week markers in text.

    Language-agnostic detection across EN / VI / FR / ES / PT / DE / IT / JP /
    KR / ZH. The check for "after_next" runs first so that overlapping markers
    (e.g. Chinese 下下周 contains 下周) are classified correctly.
    """
    if not text:
        return None
    for pat in _AFTER_NEXT_TEXT_PATTERNS:
        if pat.search(text):
            return "after_next"
    for pat in _NEXT_TEXT_PATTERNS:
        if pat.search(text):
            return "next"
    return None


# ── today / tomorrow phrase_class detection ────────────────────────────────────
#
# Targets "Case G" failures: the LLM classifies a phrase as ``phrase_class=
# "today"`` when the source text clearly says tomorrow (or vice versa), so the
# resolver computes the wrong calendar day. The same neuro-symbolic guard used
# for named_weekday offset is applied here: scan the verbatim deadline phrase
# for unambiguous tokens in any supported language and override the LLM's
# classification when it disagrees.
#
# Conservative contract:
#   - Only applied when phrase_class ∈ {"today", "tomorrow"} so generic uses of
#     "today"/"tomorrow" inside other phrase classes are not affected.
#   - If BOTH a today-marker and a tomorrow-marker are present in the same
#     ``deadline_v2.text`` (rare, e.g. "by today instead of tomorrow"), the
#     detector returns None — the text is ambiguous, trust the LLM.
#   - Vietnamese / Spanish / German use multi-char tokens to avoid colliding
#     with adjacent words ("mai" / "mañana" / "morgen" can mean other things
#     when standing alone, so we require the full deadline collocation).

_TODAY_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\btoday\b", re.IGNORECASE),
    # Vietnamese: "hôm nay" — keep two-token boundary so it cannot collide with
    # "hôm qua" (yesterday) or "hôm sau" (the next day).
    re.compile(r"\bhôm\s+nay\b", re.IGNORECASE),
    # French: "aujourd'hui" — apostrophe is non-word; use explicit word guards
    # rather than \b which would break on the apostrophe.
    re.compile(r"(?<!\w)aujourd['’]hui(?!\w)", re.IGNORECASE),
    # Spanish
    re.compile(r"\bhoy\b", re.IGNORECASE),
    # Portuguese
    re.compile(r"\bhoje\b", re.IGNORECASE),
    # German
    re.compile(r"\bheute\b", re.IGNORECASE),
    # Italian
    re.compile(r"\boggi\b", re.IGNORECASE),
    # Japanese: 今日 / きょう / 本日 ; Korean: 오늘 ; Chinese: 今天
    re.compile(r"今日|きょう|本日|오늘|今天"),
)

_TOMORROW_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\btomorrow\b", re.IGNORECASE),
    # Vietnamese: require the full "ngày mai" collocation — bare "mai" can mean
    # "May" or other things.
    re.compile(r"\bngày\s+mai\b", re.IGNORECASE),
    # French
    re.compile(r"\bdemain\b", re.IGNORECASE),
    # Spanish — "mañana" can mean morning generically, but within a deadline
    # phrase the LLM has already classified as today/tomorrow, the temporal
    # reading is the operative one.
    re.compile(r"\bmañana\b", re.IGNORECASE),
    # Portuguese (with and without diacritic for robustness)
    re.compile(r"\bamanh[ãa]\b", re.IGNORECASE),
    # German — same caveat as Spanish: "morgen" can mean morning, disambiguated
    # by the surrounding deadline class.
    re.compile(r"\bmorgen\b", re.IGNORECASE),
    # Italian
    re.compile(r"\bdomani\b", re.IGNORECASE),
    # Japanese: 明日 / あした / あす / みょうにち
    # Korean: 내일
    # Chinese: 明天 / 明日 (alt form)
    re.compile(r"明日|あした|あす|みょうにち|내일|明天"),
)


def _detect_text_day_token(text: str | None) -> str | None:
    """Return "today", "tomorrow", or None.

    Returns None when the text contains BOTH a today-marker and a
    tomorrow-marker (ambiguous), so the LLM's classification is trusted in
    that edge case rather than overridden in either direction.
    """
    if not text:
        return None
    has_today = any(p.search(text) for p in _TODAY_TEXT_PATTERNS)
    has_tomorrow = any(p.search(text) for p in _TOMORROW_TEXT_PATTERNS)
    if has_today and has_tomorrow:
        return None
    if has_today:
        return "today"
    if has_tomorrow:
        return "tomorrow"
    return None


# ── Source-text fallback for both detectors ────────────────────────────────────
#
# The LLM sometimes strips the language qualifier from ``deadline_v2.text``,
# e.g. extracting "thứ Sáu" out of the source phrase "trước thứ Sáu tới". When
# the primary scan over ``deadline_v2.text`` finds no marker, fall back to a
# small windowed scan around the deadline phrase inside the original message —
# anchored, scoped, and language-agnostic.
#
# Why a window (not the whole source): a broad scan would match unrelated
# occurrences elsewhere ("see you next month"), producing false overrides.
# A window of a few dozen characters around the deadline phrase keeps the
# detector grounded in the same clause as the temporal expression.

_SOURCE_SCAN_WINDOW_CHARS = 40


def _windowed_source_text(d_text: str | None, source_text: str | None) -> str | None:
    """Return a substring of ``source_text`` centred on the first occurrence
    of ``d_text``, padded by ``_SOURCE_SCAN_WINDOW_CHARS`` on each side.

    Returns None when either input is empty or the deadline phrase isn't
    present in the source (e.g., LLM hallucinated the phrase).
    """
    if not d_text or not source_text:
        return None
    idx = source_text.lower().find(d_text.lower())
    if idx < 0:
        return None
    start = max(0, idx - _SOURCE_SCAN_WINDOW_CHARS)
    end = min(len(source_text), idx + len(d_text) + _SOURCE_SCAN_WINDOW_CHARS)
    return source_text[start:end]


def _detect_text_offset_with_source(d_text: str | None, source_text: str | None) -> str | None:
    """``_detect_text_offset`` with a windowed fallback into ``source_text``."""
    direct = _detect_text_offset(d_text)
    if direct is not None:
        return direct
    window = _windowed_source_text(d_text, source_text)
    if window is None:
        return None
    return _detect_text_offset(window)


# ── n_days param detector ──────────────────────────────────────────────────────
#
# Targets edge_priority "within 2 days" / "trong 3 ngày" failures where the
# LLM emits ``phrase_class="n_days"`` but mis-extracts ``phrase_params.n``
# (commonly off by one, e.g. n=1 for "within 2 days"). Same neuro-symbolic
# guard as the other detectors: pull the number from the verbatim deadline
# phrase (or a windowed source scan) and override only when the text is
# unambiguous.
#
# Pattern accepts the standard duration tokens in EN/VI/FR/ES/IT/DE/JA so the
# fix is not specific to any one language. Multi-script JP/CN "日" is included
# only with an explicit Latin digit prefix to keep precision; full CJK
# numeral parsing is out of scope.

_N_DAYS_TEXT_PATTERN = re.compile(
    r"\b(\d{1,3})\s*(?:days?|ngày|jours?|giorni|días|dias|Tage|tagen)\b"
    r"|(\d{1,3})\s*日(?:間)?",
    re.IGNORECASE,
)


def _detect_text_n_days(text: str | None) -> int | None:
    """Return the duration in days extracted from ``text`` (e.g. "within 2
    days" → 2; "trong 3 ngày" → 3), or None when no such phrase is present.

    When multiple matches are found, returns the *first* — typical deadline
    phrases carry a single duration token, and earlier mentions are usually
    the operative one.
    """
    if not text:
        return None
    m = _N_DAYS_TEXT_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if 0 <= n <= _MAX_FUTURE_DAYS:
        return n
    return None


def _detect_text_n_days_with_source(
    d_text: str | None, source_text: str | None
) -> int | None:
    """``_detect_text_n_days`` with a windowed source fallback (same scoping
    as the offset detector — strict window, no full-source last resort, to
    avoid picking up unrelated numbers elsewhere in the message).
    """
    direct = _detect_text_n_days(d_text)
    if direct is not None:
        return direct
    window = _windowed_source_text(d_text, source_text)
    if window is None:
        return None
    return _detect_text_n_days(window)


def _detect_text_day_token_with_source(
    d_text: str | None, source_text: str | None
) -> str | None:
    """``_detect_text_day_token`` with two source-text fallbacks.

    Priority:
      1. Direct scan of ``deadline_v2.text``.
      2. Windowed scan around the deadline phrase in ``source_text``.
      3. Full-source scan when ``deadline_v2.text`` is empty/missing — the LLM
         can omit the verbatim phrase entirely (observed on Case G failures in
         edge_priority samples). The both-markers-no-override guard in
         ``_detect_text_day_token`` keeps the broader scan safe: if the source
         legitimately mentions both today and tomorrow, no override happens.

    Note: the broader (3) fallback is intentionally *only* enabled for the
    day-token detector. The next-week offset detector keeps its strict window
    requirement because "next"/"tới" markers are common in unrelated contexts
    (e.g. "next time", "tới giờ").
    """
    direct = _detect_text_day_token(d_text)
    if direct is not None:
        return direct
    if not source_text:
        return None
    if d_text and d_text.strip():
        window = _windowed_source_text(d_text, source_text)
        if window is None:
            return None
        return _detect_text_day_token(window)
    # No deadline phrase to anchor — scan the full source as a last resort.
    return _detect_text_day_token(source_text)


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
    """Legacy resolver: closed-set text-pattern detection for outputs without phrase_class.

    Patterns recognised (language-agnostic where the markers are unambiguous):
      - "in N days" / "trong N ngày"
      - "tomorrow" / "ngày mai"
      - VN "ngày N tháng M [năm Y]" (nth_of_month with explicit month)
      - VN "cuối tuần / tháng / quý / năm" (end_of_period)
      - EN "end of (the) week / month / quarter / year"
      - FR "fin (du|de la|de) semaine | mois | trimestre | année"
      - Closed-set weekday names (EN + VI)

    All matches are validated against the plausibility window by the caller.
    """
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

    # VN "ngày N tháng M [năm Y]" — explicit Vietnamese date phrasing.
    # Year defaults to anchor.year and rolls forward when the resulting date
    # would fall outside the plausibility window in the past.
    m_vn_date = re.search(
        r"\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?\b",
        low,
        flags=re.IGNORECASE,
    )
    if m_vn_date:
        day_n = int(m_vn_date.group(1))
        month_n = int(m_vn_date.group(2))
        year_n = int(m_vn_date.group(3)) if m_vn_date.group(3) else anchor.year
        try:
            candidate = date(year_n, month_n, day_n)
        except ValueError:
            candidate = None
        if candidate is not None:
            if m_vn_date.group(3) is None and (anchor - candidate).days > _MAX_PAST_DAYS:
                try:
                    candidate = date(year_n + 1, month_n, day_n)
                except ValueError:
                    candidate = None
            if candidate is not None:
                return candidate.isoformat()

    # End-of-period — Vietnamese
    if re.search(r"\bcuối\s+năm\b", low, flags=re.IGNORECASE):
        return date(anchor.year, 12, 31).isoformat()
    if re.search(r"\bcuối\s+quý\b", low, flags=re.IGNORECASE):
        return _end_of_quarter(anchor).isoformat()
    if re.search(r"\bcuối\s+tháng\b", low, flags=re.IGNORECASE):
        return _end_of_month(anchor).isoformat()
    if re.search(r"\bcuối\s+tuần\b", low, flags=re.IGNORECASE):
        days_to_sunday = (6 - anchor.weekday()) % 7
        return (anchor + timedelta(days=days_to_sunday)).isoformat()

    # End-of-period — English
    m_eop_en = re.search(
        r"\bend\s+of\s+(?:the\s+)?(week|month|quarter|year)\b",
        low,
        flags=re.IGNORECASE,
    )
    if m_eop_en:
        period = m_eop_en.group(1).lower()
        if period == "week":
            days_to_sunday = (6 - anchor.weekday()) % 7
            return (anchor + timedelta(days=days_to_sunday)).isoformat()
        if period == "month":
            return _end_of_month(anchor).isoformat()
        if period == "quarter":
            return _end_of_quarter(anchor).isoformat()
        if period == "year":
            return date(anchor.year, 12, 31).isoformat()

    # End-of-period — French. ``\s*`` at the end (not ``\s+``) so the elided
    # form "fin de l'année" — where there's no whitespace between ``l'`` and
    # the noun — matches the same as "fin de la semaine".
    m_eop_fr = re.search(
        r"\bfin\s+(?:du|de\s+la|de\s+l['’]|de)\s*(semaine|mois|trimestre|année|annee)\b",
        low,
        flags=re.IGNORECASE,
    )
    if m_eop_fr:
        period_fr = m_eop_fr.group(1).lower()
        if period_fr == "semaine":
            days_to_sunday = (6 - anchor.weekday()) % 7
            return (anchor + timedelta(days=days_to_sunday)).isoformat()
        if period_fr == "mois":
            return _end_of_month(anchor).isoformat()
        if period_fr == "trimestre":
            return _end_of_quarter(anchor).isoformat()
        if period_fr in ("année", "annee"):
            return date(anchor.year, 12, 31).isoformat()

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
    source_text: str | None = None,
) -> dict[str, Any]:
    """Apply deterministic resolution and arithmetic guards to ``deadline_v2``.

    Priority order:
    1. If ``phrase_class`` is present → use the phrase-class handler (v2 path).
    2. Otherwise → legacy closed-set text-pattern fallback (v1 path).
    In both cases, plausibility validation is applied afterward.

    ``source_text`` (optional): the original message body. When supplied, the
    deterministic next-week / today-tomorrow detectors fall back to a
    windowed scan around the deadline phrase in the source if the qualifier
    was stripped from ``deadline_v2.text`` by the LLM.
    """
    out = dict(deadline_v2)

    if not anchor:
        return out

    phrase_class = out.get("phrase_class")
    existing_iso = out.get("iso") if isinstance(out.get("iso"), str) else None
    d_text = out.get("text") if isinstance(out.get("text"), str) else None

    # ── Plausibility gate on any existing iso (both paths) ────────────────────
    if existing_iso and not _is_plausible(existing_iso, anchor):
        out["iso"] = None
        if out.get("type") == "exact":
            out["type"] = "relative"
        existing_iso = None

    # ── Text-based offset upgrade (named_weekday only) ────────────────────────
    # When the LLM mislabels a future-week phrase as ``offset="this"`` (or
    # omits the field), upgrade based on unambiguous next-week markers in the
    # verbatim deadline phrase or in a window around it in the source.
    # Never downgrade an explicit "next"/"after_next".
    if phrase_class == "named_weekday":
        detected = _detect_text_offset_with_source(d_text, source_text)
        if detected is not None:
            params = dict(out.get("phrase_params") or {})
            current = str(params.get("offset") or "").lower()
            should_upgrade = (
                current in ("", "this", "unknown")
                or (current == "next" and detected == "after_next")
            )
            if should_upgrade:
                params["offset"] = detected
                out["phrase_params"] = params
                # Invalidate any LLM-provided iso so the V2 handler recomputes
                # from the corrected offset rather than re-using the wrong day.
                if existing_iso is not None:
                    out["iso"] = None
                    existing_iso = None

    # ── Text-based phrase_class correction (today ↔ tomorrow) ────────────────
    # Symmetric guard for the original Case G failure: the LLM emits
    # ``phrase_class="today"`` for a "tomorrow" phrase (or vice versa). When
    # an unambiguous day-token appears in the deadline phrase or its source
    # context window in any supported language, trust the text over the LLM.
    if phrase_class in ("today", "tomorrow"):
        detected = _detect_text_day_token_with_source(d_text, source_text)
        if detected is not None and detected != phrase_class:
            out["phrase_class"] = detected
            phrase_class = detected
            # Invalidate any LLM-provided iso based on the wrong class so the
            # V2 handler recomputes from the corrected phrase_class.
            if existing_iso is not None:
                out["iso"] = None
                existing_iso = None

    # ── Text-based n_days param override ─────────────────────────────────────
    # When the LLM emits phrase_class=n_days but mis-extracts the duration
    # (e.g. n=1 for "within 2 days" — observed in edge_priority samples),
    # trust the integer present in the verbatim deadline phrase.
    if phrase_class == "n_days":
        detected_n = _detect_text_n_days_with_source(d_text, source_text)
        if detected_n is not None:
            params = dict(out.get("phrase_params") or {})
            current_n = params.get("n")
            if not isinstance(current_n, int) or current_n != detected_n:
                params["n"] = detected_n
                out["phrase_params"] = params
                if existing_iso is not None:
                    out["iso"] = None
                    existing_iso = None

    # ── Trust the LLM's absolute iso once plausibility-validated ──────────────
    # When the LLM explicitly emits ``phrase_class="absolute"`` (i.e. "this is
    # a fully-resolved calendar date, no symbolic interpretation needed") and
    # provides a valid, plausibility-checked iso, the V1 text-pattern fallback
    # below must not run. Its weekday-consistency / VN "(\d+)\s*ngày" / today /
    # tomorrow rescues are designed for v1-style output without ``phrase_class``
    # — running them on absolute output produces catastrophic regressions in
    # two reproducible ways observed in 2026-05-29 production replay:
    #
    #   (1) Text incidentally contains a weekday label that disagrees with the
    #       iso (e.g. ``"Friday, 20 June 2026"`` where 2026-06-20 is actually a
    #       Saturday — fixture-author error, or human writer error in real
    #       email). The weekday-consistency gate then overrides the correct
    #       calendar date with ``_next_weekday_on_or_after(anchor, friday)``,
    #       producing a date in the recent past relative to anchor.
    #   (2) VN text like ``"trước 09:00 ngày 16/06/2026"`` matches
    #       ``(\d+)\s*ngày`` on the ``"00 ngày"`` substring of the *time*
    #       prefix, returning ``anchor + 0 days``.
    #
    # The text-based phrase_class corrections above (named_weekday / today /
    # tomorrow / n_days) are already scoped to non-absolute classes, so an
    # absolute deadline is untouched by them. Every existing rescue test in
    # ``test_temporal_resolve.py`` exercises V1 fallback *without* phrase_class
    # — those keep working unchanged.
    if phrase_class == "absolute" and existing_iso:
        return out

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
