"""Unit tests for symbolic deadline resolution.

Two test sections:
  1. phrase_class v2 path — neuro-symbolic handlers (new)
  2. Legacy v1 path — closed-set text patterns (backward compat, unchanged)
"""
from __future__ import annotations

from datetime import date

from app.pipeline.temporal_resolve import (
    enrich_deadline_v2_with_symbolic_iso,
    parse_anchor_date,
    try_resolve_deadline_iso,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1 — phrase_class v2 path
# ═══════════════════════════════════════════════════════════════════════════════

def _v2(phrase_class: str, params=None, **kw) -> dict:
    return {"phrase_class": phrase_class, "phrase_params": params, "text": "x", **kw}


class TestNamedWeekday:
    def test_this_friday_from_thursday(self):
        anchor = date(2026, 4, 2)  # Thursday
        d = _v2("named_weekday", {"weekday": "friday", "offset": "this"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-03"

    def test_next_friday_from_thursday(self):
        anchor = date(2026, 4, 2)  # Thursday
        d = _v2("named_weekday", {"weekday": "friday", "offset": "next"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-10"

    def test_after_next_friday_from_thursday(self):
        anchor = date(2026, 4, 2)  # Thursday
        d = _v2("named_weekday", {"weekday": "friday", "offset": "after_next"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-17"

    def test_monday_from_wednesday(self):
        anchor = date(2026, 5, 6)  # Wednesday
        d = _v2("named_weekday", {"weekday": "monday", "offset": "this"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-11"  # next Monday on-or-after

    def test_same_weekday_as_anchor(self):
        anchor = date(2026, 5, 11)  # Monday
        d = _v2("named_weekday", {"weekday": "monday", "offset": "this"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-11"  # today itself

    def test_language_agnostic_weekday_normalized_by_llm(self):
        """LLM normalises "thứ Sáu tới" / "vendredi prochain" → weekday=friday, offset=next."""
        anchor = date(2026, 4, 8)  # Wednesday
        d = _v2("named_weekday", {"weekday": "friday", "offset": "next"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-17"

    def test_unknown_offset_returns_nearest(self):
        anchor = date(2026, 4, 2)  # Thursday
        d = _v2("named_weekday", {"weekday": "friday", "offset": "unknown"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-03"

    def test_invalid_weekday_name_returns_none_iso(self):
        anchor = date(2026, 4, 2)
        d = _v2("named_weekday", {"weekday": "someday", "offset": "this"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out.get("iso") in (None, "")


class TestNDays:
    def test_in_3_days(self):
        anchor = date(2026, 5, 1)
        d = _v2("n_days", {"n": 3})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-04"

    def test_in_0_days_is_today(self):
        anchor = date(2026, 5, 1)
        d = _v2("n_days", {"n": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-01"

    def test_negative_n_returns_no_iso(self):
        anchor = date(2026, 5, 1)
        d = _v2("n_days", {"n": -1})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out.get("iso") in (None, "")


class TestTomorrowToday:
    def test_tomorrow(self):
        anchor = date(2026, 5, 31)
        out = enrich_deadline_v2_with_symbolic_iso(_v2("tomorrow"), anchor)
        assert out["iso"] == "2026-06-01"

    def test_today(self):
        anchor = date(2026, 5, 12)
        out = enrich_deadline_v2_with_symbolic_iso(_v2("today"), anchor)
        assert out["iso"] == "2026-05-12"


class TestEndOfPeriod:
    def test_end_of_week_from_thursday(self):
        anchor = date(2026, 4, 2)  # Thursday → Sunday is 2026-04-05
        d = _v2("end_of_period", {"period": "week"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-05"

    def test_end_of_week_from_sunday(self):
        anchor = date(2026, 4, 5)  # Sunday → same day (delta=0)
        d = _v2("end_of_period", {"period": "week"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-05"

    def test_end_of_month_april(self):
        anchor = date(2026, 4, 10)
        d = _v2("end_of_period", {"period": "month"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-30"

    def test_end_of_month_february_non_leap(self):
        anchor = date(2026, 2, 5)
        d = _v2("end_of_period", {"period": "month"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-02-28"

    def test_end_of_quarter_q2(self):
        anchor = date(2026, 5, 12)  # Q2
        d = _v2("end_of_period", {"period": "quarter"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-06-30"

    def test_end_of_quarter_q4(self):
        anchor = date(2026, 11, 1)  # Q4
        d = _v2("end_of_period", {"period": "quarter"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-12-31"

    def test_end_of_year(self):
        anchor = date(2026, 3, 1)
        d = _v2("end_of_period", {"period": "year"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-12-31"


class TestStartOfPeriod:
    def test_start_of_this_week_from_wednesday(self):
        # offset=0 → upcoming Monday on-or-after anchor (May 6 Wed → May 11 Mon)
        anchor = date(2026, 5, 6)  # Wednesday
        d = _v2("start_of_period", {"period": "week", "offset_periods": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-11"

    def test_start_of_this_week_when_today_is_monday(self):
        # offset=0 when anchor IS Monday → same day
        anchor = date(2026, 5, 11)  # Monday
        d = _v2("start_of_period", {"period": "week", "offset_periods": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-11"

    def test_start_of_next_week_from_wednesday(self):
        # offset=1 → Monday after the upcoming Monday
        anchor = date(2026, 5, 6)  # Wednesday
        d = _v2("start_of_period", {"period": "week", "offset_periods": 1})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-18"

    def test_start_of_this_month(self):
        anchor = date(2026, 5, 12)
        d = _v2("start_of_period", {"period": "month", "offset_periods": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        # May 1 is in the past → dropped by plausibility
        assert out.get("iso") in (None, "")

    def test_start_of_next_month(self):
        anchor = date(2026, 5, 12)
        d = _v2("start_of_period", {"period": "month", "offset_periods": 1})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-06-01"

    def test_start_of_year_offset_1(self):
        anchor = date(2026, 5, 12)
        d = _v2("start_of_period", {"period": "year", "offset_periods": 1})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2027-01-01"


class TestNthOfMonth:
    def test_15th_of_current_month_future(self):
        anchor = date(2026, 5, 1)
        d = _v2("nth_of_month", {"n": 15, "month_offset": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-05-15"

    def test_15th_current_month_past_goes_to_next(self):
        anchor = date(2026, 5, 20)
        d = _v2("nth_of_month", {"n": 15, "month_offset": 0})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-06-15"

    def test_month_offset_1_explicit(self):
        anchor = date(2026, 5, 1)
        d = _v2("nth_of_month", {"n": 5, "month_offset": 1})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-06-05"


class TestNamedCulturalAndNone:
    def test_named_cultural_sets_ambiguous(self):
        anchor = date(2026, 5, 1)
        d = _v2("named_cultural", {"name": "Tết"})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out.get("iso") in (None, "")
        assert out.get("is_ambiguous") is True

    def test_none_class_no_iso(self):
        anchor = date(2026, 5, 1)
        d = _v2("none")
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out.get("iso") in (None, "")

    def test_absolute_class_preserves_llm_iso(self):
        anchor = date(2026, 5, 1)
        d = _v2("absolute", iso="2026-06-15", type="exact")
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-06-15"


class TestPlausibilityWithPhraseClass:
    def test_far_future_blocked_even_with_phrase_class(self):
        anchor = date(2026, 5, 1)
        # n_days with absurd n — blocked by _MAX_FUTURE_DAYS in handler
        d = _v2("n_days", {"n": 400})
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out.get("iso") in (None, "")

    def test_no_anchor_no_resolution(self):
        d = _v2("n_days", {"n": 3})
        out = enrich_deadline_v2_with_symbolic_iso(d, None)
        assert out.get("iso") in (None, "")


def test_parse_anchor_date_iso_prefix():
    assert parse_anchor_date("2025-03-10T12:00:00Z") == date(2025, 3, 10)
    assert parse_anchor_date("invalid") is None
    assert parse_anchor_date(None) is None


def test_in_n_days_english():
    anchor = date(2025, 3, 10)
    d = {"text": "in 3 days"}
    assert try_resolve_deadline_iso(d, anchor) == "2025-03-13"


def test_in_n_days_vietnamese():
    anchor = date(2025, 3, 10)
    d = {"text": "sau 5 ngày"}
    assert try_resolve_deadline_iso(d, anchor) == "2025-03-15"


def test_next_weekday_english():
    anchor = date(2025, 3, 10)  # Monday
    d = {"text": "due Monday"}
    assert try_resolve_deadline_iso(d, anchor) == "2025-03-10"


def test_next_weekday_vietnamese():
    anchor = date(2025, 3, 10)  # Monday
    d = {"text": "deadline thứ sáu"}
    assert try_resolve_deadline_iso(d, anchor) == "2025-03-14"


def test_tomorrow_english_and_vietnamese():
    anchor = date(2026, 4, 1)
    assert try_resolve_deadline_iso({"text": "due tomorrow"}, anchor) == "2026-04-02"
    assert try_resolve_deadline_iso({"text": "hạn ngày mai"}, anchor) == "2026-04-02"


def test_v1_resolver_still_skips_ambiguous_open_ended_phrases():
    """The V1 fallback resolves explicit period markers (end_of_period etc.)
    via the patterns added in Section 5b, but genuinely ambiguous phrases —
    where the period boundary is not stated (e.g. "early next week") — still
    return None so the upstream V2 path / quality gate decides what to do.
    """
    anchor = date(2026, 4, 6)
    assert try_resolve_deadline_iso({"text": "early next week"}, anchor) is None
    assert try_resolve_deadline_iso({"text": "sometime soon"}, anchor) is None
    assert try_resolve_deadline_iso({"text": "later this quarter"}, anchor) is None


def test_enrich_fills_iso_when_missing():
    anchor = date(2025, 3, 10)
    d = {"text": "in 1 days", "type": "relative"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2025-03-11"
    assert out["type"] == "relative"


def test_enrich_no_anchor_no_change():
    d = {"text": "in 2 days"}
    out = enrich_deadline_v2_with_symbolic_iso(d, None)
    assert "iso" not in out or out.get("iso") in (None, "")


def test_enrich_preserves_existing_iso_within_window():
    anchor = date(2025, 3, 10)
    d = {"text": "later this cycle", "iso": "2025-04-01"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2025-04-01"


def test_enrich_drops_far_future_iso_from_llm():
    """Plausibility validator: implausibly far iso is dropped so the pipeline can abstain."""
    anchor = date(2026, 4, 1)
    d = {"text": "sắp tới", "iso": "2099-01-01", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out.get("iso") in (None, "")
    assert out.get("type") != "exact"


def test_enrich_drops_far_past_iso_from_llm():
    anchor = date(2026, 4, 1)
    d = {"text": "lịch sử", "iso": "2000-01-01", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out.get("iso") in (None, "")


def test_weekday_gate_corrects_iso_off_by_one_vi():
    """Systematic bug in clean eval batch: LLM resolves 'thứ Sáu' to a Saturday iso.

    Anchor 2026-04-02 is Thursday; 'trước thứ Sáu' must fall on Friday
    2026-04-03. The LLM's 2026-04-04 (Saturday) is a +1 day arithmetic
    error that used to pass the plausibility window. The weekday gate
    overrides with the symbolic next-Friday-on-or-after.
    """
    anchor = date(2026, 4, 2)
    d = {"text": "trước thứ Sáu", "iso": "2026-04-04", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


def test_weekday_gate_corrects_iso_off_by_one_en():
    anchor = date(2026, 3, 31)  # Tuesday
    d = {"text": "by this Friday", "iso": "2026-04-04", "type": "relative"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


def test_non_weekday_symbolic_gate_corrects_existing_iso_for_tomorrow():
    anchor = date(2026, 4, 6)
    d = {"text": "trước ngày mai", "iso": "2026-04-06", "type": "relative"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-07"


def test_non_weekday_symbolic_gate_corrects_existing_iso_for_n_days():
    anchor = date(2026, 3, 30)
    d = {"text": "trong 7 ngày", "iso": "2026-04-05", "type": "relative"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-06"


def test_weekday_gate_respects_tới_next_week_when_weekday_matches():
    """If the LLM chose next week's Friday for 'thứ Sáu tới', the gate must NOT
    override — the weekday is already correct and 'tới' semantics are
    language-level, not arithmetic."""
    anchor = date(2026, 4, 2)  # Thursday
    d = {"text": "trước thứ Sáu tới", "iso": "2026-04-10", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-10"


def test_weekday_gate_noop_when_phrase_has_no_weekday():
    """Open-set phrases still have no gate applied — only phrases with a
    closed-set weekday name trigger the arithmetic check."""
    anchor = date(2026, 4, 2)
    d = {"text": "cuối tuần", "iso": "2026-04-05", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-05"


def test_weekday_gate_preserves_correct_iso():
    """A correct iso on the right weekday must be left alone."""
    anchor = date(2026, 4, 2)
    d = {"text": "trước thứ Sáu", "iso": "2026-04-03", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


# ---------------------------------------------------------------------------
# phrase_class="absolute" short-circuit (2026-05-29 production replay finding)
# ---------------------------------------------------------------------------
# When the LLM emits ``phrase_class="absolute"`` it is asserting "this is a
# fully-resolved calendar date". The V1 text-pattern fallback's weekday gate
# and VN "(\d+)\s*ngày" detector were designed for legacy v1 output without
# phrase_class and produce catastrophic regressions if allowed to run on
# absolute output (see the 4 replay cases reproduced below). The
# short-circuit added in this commit returns the LLM's iso unchanged once
# the plausibility gate has validated it. Plausibility-failed or missing iso
# still falls through to the V1 rescue paths.

def test_absolute_iso_preserved_when_text_weekday_mismatches_actual_date():
    """Replay case: 'Friday, 20 June 2026' from the dogfood fixture. The
    writer mislabelled the weekday — 2026-06-20 is actually a Saturday —
    but the calendar date is what matters. Pre-fix, the weekday-consistency
    gate computed next-Friday-on-or-after the anchor (2026-05-29) and
    silently overrode 2026-06-20."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "Friday, 20 June 2026, 3:00 PM",
        "resolved_from": "Friday, 20 June 2026, 3:00 PM",
        "iso": "2026-06-20",
        "type": "exact",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-06-20"


def test_absolute_iso_preserved_for_tuesday_label_off_by_one():
    """Replay case: 'Tuesday, 10 June 2026' — 2026-06-10 is a Wednesday.
    The calendar date stays."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "Tuesday, 10 June 2026",
        "iso": "2026-06-10",
        "type": "exact",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-06-10"


def test_absolute_iso_preserved_when_short_text_has_weekday_label():
    """Replay case: 'Monday 9 June' (short form) — 2026-06-09 is a Tuesday."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "Monday 9 June",
        "iso": "2026-06-09",
        "type": "exact",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-06-09"


def test_absolute_iso_preserved_for_vn_time_prefixed_date():
    """Replay case: 'trước 09:00 ngày 16/06/2026'. Pre-fix, the legacy
    closed-set detector's ``(\\d+)\\s*ngày`` regex matched the ``"00 ngày"``
    substring of the time prefix and returned ``anchor + 0 days``
    (2026-05-23). With the short-circuit, the LLM's 2026-06-16 is trusted."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "trước 09:00 ngày 16/06/2026",
        "iso": "2026-06-16",
        "type": "exact",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-06-16"


def test_absolute_iso_implausible_still_nulled_by_plausibility_gate():
    """Guard: the short-circuit only fires AFTER the plausibility gate. An
    LLM-emitted absolute iso far outside the anchor window is still nulled
    (so downstream consumers know it was rejected)."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "1 Jan 2099",
        "iso": "2099-01-01",
        "type": "exact",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] is None


def test_absolute_phrase_class_with_no_iso_falls_through_to_v1():
    """Guard: when phrase_class='absolute' is set but the LLM didn't emit an
    iso, the short-circuit must NOT fire — V1 rescue paths still get a
    chance to construct one from the text."""
    anchor = date(2026, 5, 23)
    d = {
        "text": "trong 3 ngày",
        "iso": None,
        "type": "none",
        "phrase_class": "absolute",
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    # V1's "(\d+)\s*ngày" detector should have rescued anchor + 3 days.
    assert out["iso"] == "2026-05-26"


# ---------------------------------------------------------------------------
# week_offset: "next" and "after_next" override (D.2 — Q-01 roadmap)
# ---------------------------------------------------------------------------

def test_week_offset_next_overrides_this_friday():
    """'thứ Sáu tới' (next Friday) from anchor Thu 2026-04-02.

    Without week_offset the gate keeps the nearest Friday (2026-04-03).
    With week_offset='next' the arithmetic must produce the following week
    (2026-04-10 = 2026-04-03 + 7).

    This covers the dominant error class in the full 250-sample eval where
    'thứ Sáu tới' was predicted as 2026-04-03 instead of 2026-04-10.
    """
    anchor = date(2026, 4, 2)  # Thursday
    d = {"text": "trước thứ Sáu tới", "iso": "2026-04-03", "type": "exact", "week_offset": "next"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-10"


def test_week_offset_next_english():
    """'next Friday' from anchor Wed 2026-04-08 → 2026-04-17."""
    anchor = date(2026, 4, 8)  # Wednesday
    d = {"text": "by next Friday", "iso": "2026-04-10", "type": "relative", "week_offset": "next"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-17"


def test_week_offset_after_next():
    """'after_next Friday' from anchor Thu 2026-04-02 → 2026-04-17 (nearest + 14)."""
    anchor = date(2026, 4, 2)  # Thursday; nearest Friday = 2026-04-03
    d = {"text": "thứ Sáu sau nữa", "iso": None, "type": "relative", "week_offset": "after_next"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-17"


def test_week_offset_this_uses_existing_gate():
    """week_offset='this' still applies the weekday consistency gate for arithmetic errors."""
    anchor = date(2026, 4, 2)  # Thursday
    # LLM gave Saturday (+1 day error), week_offset='this' → gate corrects to Friday
    d = {"text": "thứ Sáu này", "iso": "2026-04-04", "type": "exact", "week_offset": "this"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


def test_week_offset_unknown_does_not_change_correct_iso():
    """week_offset='unknown' leaves a correct iso alone (no offset applied)."""
    anchor = date(2026, 4, 2)  # Thursday
    d = {"text": "thứ Sáu", "iso": "2026-04-03", "type": "exact", "week_offset": "unknown"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


def test_week_offset_next_with_missing_iso():
    """LLM left iso=null (as instructed for weekday phrases); week_offset='next' fills it."""
    anchor = date(2026, 4, 2)  # Thursday; nearest Friday = 2026-04-03
    d = {"text": "thứ Sáu tới", "iso": None, "type": "relative", "week_offset": "next"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-10"


def test_week_offset_none_preserves_original_gate_behavior():
    """No week_offset → existing weekday gate behavior unchanged (backward compat)."""
    anchor = date(2026, 4, 2)  # Thursday
    # LLM gave Saturday (+1 day error), no week_offset → gate corrects to Friday
    d = {"text": "thứ Sáu", "iso": "2026-04-04", "type": "exact"}
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-03"


# ---------------------------------------------------------------------------
# V2 fallback to V1 and cross-path phrase_params.offset hint
# ---------------------------------------------------------------------------

def test_v2_fallback_to_v1_when_phrase_params_missing():
    """When phrase_class is set but phrase_params is None, V2 resolution fails.
    The resolver must fall through to V1 text-pattern rescue.

    Previously: V2 path returned early with iso=None regardless.
    Now: failed V2 falls through so V1 can still resolve via text.
    """
    anchor = date(2026, 4, 2)  # Thursday
    d = {
        "phrase_class": "named_weekday",
        "phrase_params": None,        # V2 will fail
        "text": "tomorrow",
        "iso": None,
        "type": "relative",
        "week_offset": None,
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    # V1 catches "tomorrow" → anchor + 1
    assert out["iso"] == "2026-04-03"


def test_v1_uses_phrase_params_offset_when_week_offset_null():
    """When week_offset=null (new prompt style) and V2 fails due to bad
    phrase_params.weekday, V1 must still read phrase_params.offset as a
    hint so the weekday offset intent is not lost.

    Scenario: LLM outputs phrase_class=named_weekday, offset=next,
    weekday=None (invalid).  V2 fails; V1 finds 'thứ sáu' in text and
    applies the 'next' offset from phrase_params.
    """
    anchor = date(2026, 4, 2)  # Thursday; nearest Friday = 2026-04-03
    d = {
        "phrase_class": "named_weekday",
        "phrase_params": {"weekday": None, "offset": "next"},  # weekday invalid
        "text": "thứ Sáu tới",
        "iso": None,
        "type": "relative",
        "week_offset": None,
    }
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    # V1 finds "thứ sáu", offset="next" from phrase_params → nearest+7
    assert out["iso"] == "2026-04-10"


def test_v2_named_weekday_overrides_llm_iso_with_anchor_plus_one_for_tomorrow():
    """phrase_class='tomorrow' must always compute anchor+1, even if LLM
    mistakenly set iso=anchor (today).

    Root cause of off-by-one errors in edge_priority category: LLM outputs
    iso=sent_at for 'tomorrow' phrases; V2 deterministic path corrects it.
    """
    anchor = date(2026, 4, 7)  # Tuesday
    d = _v2("tomorrow", iso=anchor.isoformat(), type="exact")
    out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
    assert out["iso"] == "2026-04-08"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3 — text-based next-week offset upgrade
# ═══════════════════════════════════════════════════════════════════════════════
# Targets the wrong_deadline failure mode where the LLM emits
# ``phrase_class="named_weekday"`` with ``offset="this"`` even though the
# source text carries a clear future-week qualifier ("next", "tới",
# "prochain", 来週, …). The deterministic detector must recognise these
# markers in any of the supported languages and never downgrade an explicit
# ``offset="next"`` the LLM got right.


class TestTextBasedOffsetUpgrade:
    """Anchor: Thursday 2026-04-02. This-Friday=04-03, next-Friday=04-10."""

    ANCHOR = date(2026, 4, 2)

    def _weekday(self, text: str, offset: str | None = "this") -> dict:
        params = {"weekday": "friday"}
        if offset is not None:
            params["offset"] = offset
        return {
            "phrase_class": "named_weekday",
            "phrase_params": params,
            "text": text,
        }

    # ── Upgrade: this → next when text says next ──────────────────────────────

    def test_english_next_friday_upgrades_offset(self):
        d = self._weekday("by next Friday")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"
        assert out["phrase_params"]["offset"] == "next"

    def test_vietnamese_thu_sau_toi_upgrades_offset(self):
        d = self._weekday("trước thứ Sáu tới")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_vietnamese_tuan_sau_upgrades_offset(self):
        d = self._weekday("thứ Sáu tuần sau")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_french_vendredi_prochain_upgrades_offset(self):
        d = self._weekday("vendredi prochain")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_french_feminine_prochaine_upgrades_offset(self):
        d = self._weekday("la semaine prochaine vendredi")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_spanish_proximo_upgrades_offset(self):
        d = self._weekday("el próximo viernes")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_portuguese_ascii_proxima_upgrades_offset(self):
        d = self._weekday("proxima sexta")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_german_naechsten_upgrades_offset(self):
        d = self._weekday("nächsten Freitag")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_german_ascii_fallback_naechsten_upgrades_offset(self):
        d = self._weekday("naechsten Freitag")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_italian_prossimo_upgrades_offset(self):
        d = self._weekday("prossimo venerdì")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_japanese_raishuu_upgrades_offset(self):
        d = self._weekday("来週の金曜日")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_korean_daeum_ju_upgrades_offset(self):
        d = self._weekday("다음 주 금요일")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_chinese_xia_zhou_upgrades_offset(self):
        d = self._weekday("下周五")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_missing_offset_field_upgrades_to_next_when_text_says_so(self):
        d = self._weekday("next Friday", offset=None)
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"
        assert out["phrase_params"]["offset"] == "next"

    def test_unknown_offset_upgrades_to_next(self):
        d = self._weekday("next Friday", offset="unknown")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    def test_llm_iso_is_invalidated_when_offset_upgraded(self):
        """An LLM-provided iso based on the wrong offset must not survive
        the upgrade — recomputation from the corrected offset is authoritative.
        """
        d = self._weekday("next Friday")
        d["iso"] = "2026-04-03"  # the wrong "this Friday" iso
        d["type"] = "exact"
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"

    # ── Upgrade: this → after_next when text signals two weeks out ────────────

    def test_english_after_next_upgrades_offset(self):
        d = self._weekday("the Friday after next")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-17"

    def test_vietnamese_sau_nua_upgrades_offset(self):
        d = self._weekday("thứ Sáu sau nữa")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-17"

    def test_japanese_saraishuu_upgrades_offset(self):
        d = self._weekday("再来週金曜日")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-17"

    def test_chinese_xia_xia_zhou_upgrades_offset(self):
        d = self._weekday("下下周五")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-17"

    def test_explicit_next_upgrades_to_after_next_when_text_says_so(self):
        """If the LLM emitted offset="next" but the text actually signals
        "after_next", honour the stronger marker."""
        d = self._weekday("the Friday after next", offset="next")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-17"

    # ── No-op: never downgrade or alter unrelated phrases ────────────────────

    def test_bare_weekday_no_qualifier_stays_this(self):
        d = self._weekday("by Friday")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-03"
        assert out["phrase_params"]["offset"] == "this"

    def test_vietnamese_this_friday_stays_this(self):
        # "thứ Sáu này" — "này" means "this", not a next qualifier.
        d = self._weekday("thứ Sáu này")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-03"

    def test_explicit_next_never_downgraded(self):
        # No next-marker in text, but LLM correctly emitted offset=next.
        d = self._weekday("Friday", offset="next")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"
        assert out["phrase_params"]["offset"] == "next"

    def test_detector_does_not_affect_non_named_weekday_classes(self):
        """A "next time" inside a 'tomorrow' phrase must not be misinterpreted."""
        d = {
            "phrase_class": "tomorrow",
            "phrase_params": None,
            "text": "next time, by tomorrow",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-03"  # anchor + 1

    def test_word_boundary_avoids_substring_false_positives(self):
        # "nextstep" or "context" must not trigger an upgrade for "next".
        d = self._weekday("context-switch by Friday")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-03"
        assert out["phrase_params"]["offset"] == "this"

    def test_chinese_xia_xia_does_not_falsely_match_xia(self):
        """下下周 must classify as after_next, not next — overlap guard."""
        d = self._weekday("下下周五")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["phrase_params"]["offset"] == "after_next"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4 — text-based today / tomorrow phrase_class correction
# ═══════════════════════════════════════════════════════════════════════════════
# Targets the "Case G" failure mode where the LLM emits ``phrase_class=
# "today"`` for a tomorrow phrase (or vice versa). The deterministic detector
# must recognise day-tokens in any of the supported languages and override
# symmetrically without ever firing when the class is unrelated.


class TestTextBasedDayTokenCorrection:
    """Anchor: Tuesday 2026-04-07. today=04-07, tomorrow=04-08."""

    ANCHOR = date(2026, 4, 7)

    def _day(self, phrase_class: str, text: str) -> dict:
        return {
            "phrase_class": phrase_class,
            "phrase_params": None,
            "text": text,
        }

    # ── Override: today → tomorrow (LLM mislabel of a tomorrow phrase) ────────

    def test_english_tomorrow_overrides_today(self):
        d = self._day("today", "by tomorrow")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    def test_vietnamese_ngay_mai_overrides_today(self):
        d = self._day("today", "trước ngày mai")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_french_demain_overrides_today(self):
        d = self._day("today", "avant demain")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_spanish_manana_overrides_today(self):
        d = self._day("today", "para mañana")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_portuguese_amanha_overrides_today(self):
        d = self._day("today", "até amanhã")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_portuguese_ascii_amanha_overrides_today(self):
        d = self._day("today", "ate amanha")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_german_morgen_overrides_today(self):
        d = self._day("today", "bis morgen")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_italian_domani_overrides_today(self):
        d = self._day("today", "entro domani")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_japanese_ashita_overrides_today(self):
        d = self._day("today", "明日まで")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_japanese_hiragana_overrides_today(self):
        d = self._day("today", "あしたまで")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_korean_naeil_overrides_today(self):
        d = self._day("today", "내일까지")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    def test_chinese_mingtian_overrides_today(self):
        d = self._day("today", "明天之前")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"

    # ── Override: tomorrow → today (LLM mislabel of a today phrase) ───────────

    def test_english_today_overrides_tomorrow(self):
        d = self._day("tomorrow", "by today")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    def test_vietnamese_hom_nay_overrides_tomorrow(self):
        d = self._day("tomorrow", "ngay hôm nay")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_french_aujourdhui_overrides_tomorrow(self):
        d = self._day("tomorrow", "avant aujourd'hui")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_french_aujourdhui_curly_apostrophe_overrides_tomorrow(self):
        d = self._day("tomorrow", "avant aujourd’hui")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_spanish_hoy_overrides_tomorrow(self):
        d = self._day("tomorrow", "para hoy")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_portuguese_hoje_overrides_tomorrow(self):
        d = self._day("tomorrow", "até hoje")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_german_heute_overrides_tomorrow(self):
        d = self._day("tomorrow", "bis heute")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_italian_oggi_overrides_tomorrow(self):
        d = self._day("tomorrow", "entro oggi")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_japanese_kyou_overrides_tomorrow(self):
        d = self._day("tomorrow", "今日まで")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_korean_oneul_overrides_tomorrow(self):
        d = self._day("tomorrow", "오늘까지")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    def test_chinese_jintian_overrides_tomorrow(self):
        d = self._day("tomorrow", "今天之前")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"

    # ── No-op: correct class stays unchanged ──────────────────────────────────

    def test_today_with_today_marker_no_op(self):
        d = self._day("today", "by today")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    def test_tomorrow_with_tomorrow_marker_no_op(self):
        d = self._day("tomorrow", "by tomorrow")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    def test_today_with_no_marker_stays(self):
        # E.g., LLM extracted today from "EOD" or context with no word marker.
        d = self._day("today", "EOD")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    # ── Conservative: ambiguous text leaves LLM classification alone ──────────

    def test_both_markers_present_no_override(self):
        """'by today instead of tomorrow' has both markers → trust LLM."""
        d = self._day("today", "by today instead of tomorrow")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    def test_both_markers_present_tomorrow_class_no_override(self):
        d = self._day("tomorrow", "not today but tomorrow")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    # ── Scope: detector never fires for unrelated phrase_class ────────────────

    def test_detector_does_not_fire_for_named_weekday(self):
        # "today" in description of a named_weekday phrase must be ignored.
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "today's deadline is Friday",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # Should resolve to this Friday (April 10), not today (April 7)
        assert out["iso"] == "2026-04-10"
        assert out["phrase_class"] == "named_weekday"

    def test_detector_does_not_fire_for_n_days(self):
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 3},
            "text": "within 3 days from today",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-10"  # anchor + 3
        assert out["phrase_class"] == "n_days"

    # ── LLM iso invalidation on override ──────────────────────────────────────

    def test_llm_iso_invalidated_when_class_overridden(self):
        """An LLM-provided iso based on the wrong class must be recomputed."""
        d = self._day("today", "by tomorrow")
        d["iso"] = "2026-04-07"  # the wrong "today" iso
        d["type"] = "exact"
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    # ── Vietnamese guards: "mai" / "hôm" alone must NOT trigger ──────────────

    def test_vietnamese_bare_mai_does_not_trigger(self):
        """'tháng mai' or just 'mai' (May) should not be misread as tomorrow."""
        d = self._day("today", "tháng mai")  # "May" the month
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # No override → stays as today
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    def test_vietnamese_hom_qua_does_not_trigger_today(self):
        """'hôm qua' (yesterday) must NOT be matched as 'hôm nay'."""
        d = self._day("tomorrow", "từ hôm qua")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # No override → stays as tomorrow
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    # ── Empty / missing text ─────────────────────────────────────────────────

    def test_missing_text_no_override(self):
        d = {"phrase_class": "today", "phrase_params": None, "text": None}
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    def test_empty_text_no_override(self):
        d = self._day("today", "")
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5 — Source-text windowed fallback for both detectors
# ═══════════════════════════════════════════════════════════════════════════════
# Covers the failure mode where the LLM strips the language qualifier from
# ``deadline_v2.text`` (e.g. extracting "thứ Sáu" from "trước thứ Sáu tới").
# The windowed scan over the original source text rescues the detector — but
# only within a small window around the deadline phrase so unrelated tokens
# elsewhere in the message do not produce false overrides.


class TestSourceTextFallback:
    """Anchor: Thursday 2026-04-02 (next Friday = 04-10, after_next = 04-17).
    For day-token tests anchor switches to Tuesday 2026-04-07.
    """

    WEEKDAY_ANCHOR = date(2026, 4, 2)
    DAY_ANCHOR = date(2026, 4, 7)

    # ── Offset detector: source rescues stripped "tới" / "next" ──────────────

    def test_source_fallback_recovers_vietnamese_toi_stripped_from_text(self):
        """LLM produced text='thứ Sáu' but source has 'trước thứ Sáu tới'."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "thứ Sáu",
        }
        source = "@Hoàng: update Q1 report asap, deadline là trước thứ Sáu tới."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        assert out["iso"] == "2026-04-10"
        assert out["phrase_params"]["offset"] == "next"

    def test_source_fallback_recovers_english_next_stripped_from_text(self):
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Friday",
        }
        source = "Please ship the report by next Friday, thanks."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        assert out["iso"] == "2026-04-10"

    def test_source_fallback_recovers_french_prochain(self):
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "vendredi",
        }
        source = "Merci d'envoyer le rapport vendredi prochain."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        assert out["iso"] == "2026-04-10"

    def test_source_fallback_recovers_after_next(self):
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Friday",
        }
        source = "Submit it the Friday after next, latest."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        assert out["iso"] == "2026-04-17"

    # ── Day-token detector: source rescues stripped tomorrow/today ────────────

    def test_source_fallback_recovers_tomorrow_stripped_from_text(self):
        """LLM extracted text='due' but source has 'due tomorrow'."""
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": "due",
        }
        source = "[URGENT] Paul, please update the report — due tomorrow."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.DAY_ANCHOR, source)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    def test_source_fallback_recovers_vietnamese_ngay_mai(self):
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": "trước",
        }
        source = "[GẤP] Phạm Hương ơi, gửi wireframe trang chủ trước ngày mai."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.DAY_ANCHOR, source)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    # ── Scope guard: far-away markers must NOT trigger ───────────────────────

    def test_far_away_next_in_source_does_not_trigger_override(self):
        """A 'next month' 100+ chars away from the deadline phrase must NOT
        be picked up by the windowed scan."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Friday",
        }
        # 'next' appears 100+ chars before "Friday"
        source = (
            "Hi team — quick reminder that next month we'll have the all-hands "
            "and a few other team events to prepare for. Separately, please "
            "submit the report by Friday."
        )
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        # Window should not reach "next month" → stays as this Friday
        assert out["iso"] == "2026-04-03"
        assert out["phrase_params"]["offset"] == "this"

    def test_far_away_tomorrow_in_source_does_not_override_today(self):
        """A 'tomorrow' far from the deadline phrase must not affect class."""
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": "EOD",
        }
        source = (
            "We can plan the migration for tomorrow if it helps, but for the "
            "immediate task: please push the hotfix and confirm done by EOD."
        )
        out = enrich_deadline_v2_with_symbolic_iso(d, self.DAY_ANCHOR, source)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_class"] == "today"

    # ── Edge cases: phrase not in source, no source, etc. ────────────────────

    def test_deadline_phrase_not_in_source_no_override(self):
        """If deadline_v2.text doesn't appear in source (LLM hallucination),
        the fallback returns None and no override happens."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Wednesday",  # not present in source below
        }
        source = "Please ship by next Friday."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        # No anchor in source → no fallback → offset stays "this"
        assert out["phrase_params"]["offset"] == "this"

    def test_no_source_text_still_works_via_direct_scan(self):
        """When source_text is None, the existing direct scan still applies."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "thứ Sáu tới",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, None)
        assert out["iso"] == "2026-04-10"

    def test_empty_source_text_no_fallback(self):
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Friday",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, "")
        assert out["phrase_params"]["offset"] == "this"

    def test_day_token_fallback_to_full_source_when_d_text_empty(self):
        """Edge-priority Case G: LLM emits phrase_class=today with d_text=None
        for a phrase like 'trước ngày mai'. The full-source last-resort scan
        catches the tomorrow marker and overrides."""
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": None,
        }
        source = "[GẤP] Phạm Hương ơi, gửi wireframe trang chủ trước ngày mai. Rất gấp!"
        # Tuesday 2026-03-31 → tomorrow = 2026-04-01
        out = enrich_deadline_v2_with_symbolic_iso(d, date(2026, 3, 31), source)
        assert out["iso"] == "2026-04-01"
        assert out["phrase_class"] == "tomorrow"

    def test_day_token_fallback_to_full_source_english_tomorrow(self):
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": "",
        }
        source = "[URGENT] Paul, please update the API documentation by tomorrow. This is critical!"
        out = enrich_deadline_v2_with_symbolic_iso(d, date(2026, 4, 7), source)
        assert out["iso"] == "2026-04-08"
        assert out["phrase_class"] == "tomorrow"

    def test_day_token_full_source_fallback_respects_both_markers_guard(self):
        """If source mentions BOTH today and tomorrow, no override (ambiguous)."""
        d = {
            "phrase_class": "today",
            "phrase_params": None,
            "text": None,
        }
        source = "Note: not today but tomorrow is the deadline."
        out = enrich_deadline_v2_with_symbolic_iso(d, date(2026, 4, 7), source)
        # Both markers → no override → stays as today
        assert out["phrase_class"] == "today"
        assert out["iso"] == "2026-04-07"

    def test_day_token_no_fallback_when_source_also_empty(self):
        d = {"phrase_class": "today", "phrase_params": None, "text": None}
        out = enrich_deadline_v2_with_symbolic_iso(d, date(2026, 4, 7), None)
        assert out["iso"] == "2026-04-07"

    def test_offset_detector_does_not_get_broader_full_source_fallback(self):
        """The next-week detector intentionally stays strict (windowed only).
        Empty d_text + source full of 'next' tokens elsewhere must NOT trigger
        offset upgrade."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": None,
        }
        source = "We'll have the next sync next week to plan things — meanwhile by Friday please ship the bug fix."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        # No windowed anchor → no override → stays as this Friday
        assert out["phrase_params"]["offset"] == "this"

    def test_direct_scan_wins_over_source_when_both_have_markers(self):
        """If deadline_v2.text already carries the qualifier, use it directly
        without scanning the source — saves work and avoids ambiguity."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "next Friday",
        }
        # Source happens to also have an "after next" marker far away; direct
        # scan over text returns "next" first, source isn't consulted.
        source = "Long-term plan: deliver the Friday after next. Short-term: by next Friday."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.WEEKDAY_ANCHOR, source)
        assert out["iso"] == "2026-04-10"  # next Friday from direct scan
        assert out["phrase_params"]["offset"] == "next"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5b — V1 legacy resolver: extended patterns
# ═══════════════════════════════════════════════════════════════════════════════
# Covers the failure mode where the LLM emits ``deadline_v2.text`` carrying a
# universal temporal expression but omits ``phrase_class``/``phrase_params``
# (so the V2 handler is skipped). Patterns added here are language-agnostic
# in the sense that each pattern uses standard markers for that language —
# none of them target a specific dataset string.


class TestV1NthOfMonthVietnamese:
    """`ngày N tháng M [năm Y]` is a universal Vietnamese date expression."""

    def test_ngay_thang_in_future_same_year(self):
        anchor = date(2026, 4, 1)
        out = try_resolve_deadline_iso({"text": "trước ngày 10 tháng 4"}, anchor)
        assert out == "2026-04-10"

    def test_ngay_thang_with_explicit_year(self):
        anchor = date(2026, 4, 1)
        out = try_resolve_deadline_iso({"text": "ngày 15 tháng 8 năm 2027"}, anchor)
        assert out == "2027-08-15"

    def test_ngay_thang_rolls_forward_when_past(self):
        # Anchor is May; "ngày 10 tháng 4" without year would be in the past —
        # roll forward to next year.
        anchor = date(2026, 5, 20)
        out = try_resolve_deadline_iso({"text": "ngày 10 tháng 4"}, anchor)
        assert out == "2027-04-10"

    def test_ngay_thang_today_does_not_roll(self):
        # Same-day boundary: today should not roll into next year.
        anchor = date(2026, 4, 10)
        out = try_resolve_deadline_iso({"text": "ngày 10 tháng 4"}, anchor)
        assert out == "2026-04-10"

    def test_ngay_thang_invalid_date_returns_none(self):
        anchor = date(2026, 4, 1)
        # April has 30 days; ngày 31 tháng 4 is invalid.
        out = try_resolve_deadline_iso({"text": "ngày 31 tháng 4"}, anchor)
        assert out is None


class TestV1EndOfPeriod:
    """`cuối X` / `end of X` / `fin de X` — multi-language end-of-period."""

    # ── Vietnamese ────────────────────────────────────────────────────────────

    def test_cuoi_tuan_resolves_to_sunday(self):
        # Anchor 2026-04-06 is a Monday → Sunday is 2026-04-12.
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "trước cuối tuần"}, anchor)
        assert out == "2026-04-12"

    def test_cuoi_thang_resolves_to_last_day(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "trước cuối tháng"}, anchor)
        assert out == "2026-04-30"

    def test_cuoi_quy_resolves_to_quarter_end(self):
        anchor = date(2026, 4, 6)  # Q2 → 2026-06-30
        out = try_resolve_deadline_iso({"text": "trước cuối quý"}, anchor)
        assert out == "2026-06-30"

    def test_cuoi_nam_resolves_to_year_end(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "trước cuối năm"}, anchor)
        assert out == "2026-12-31"

    # ── English ───────────────────────────────────────────────────────────────

    def test_end_of_week_resolves_to_sunday(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "by end of week"}, anchor)
        assert out == "2026-04-12"

    def test_end_of_the_month_resolves_to_last_day(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "by end of the month"}, anchor)
        assert out == "2026-04-30"

    def test_end_of_quarter_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "end of quarter"}, anchor)
        assert out == "2026-06-30"

    def test_end_of_year_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "end of year"}, anchor)
        assert out == "2026-12-31"

    # ── French ────────────────────────────────────────────────────────────────

    def test_fin_du_mois_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "avant la fin du mois"}, anchor)
        assert out == "2026-04-30"

    def test_fin_de_la_semaine_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "avant la fin de la semaine"}, anchor)
        assert out == "2026-04-12"

    def test_fin_du_trimestre_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "avant la fin du trimestre"}, anchor)
        assert out == "2026-06-30"

    def test_fin_de_annee_resolves(self):
        anchor = date(2026, 4, 6)
        out = try_resolve_deadline_iso({"text": "avant la fin de l'année"}, anchor)
        assert out == "2026-12-31"


class TestNDaysParamOverride:
    """phrase_class=n_days mis-extraction: LLM emits wrong n; detector pulls
    the correct integer from the verbatim text (or windowed source)."""

    ANCHOR = date(2026, 4, 2)

    def test_english_within_n_days_overrides_wrong_n(self):
        """'within 2 days' → expected anchor+2 even when LLM emits n=1."""
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 1},
            "text": "within 2 days",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-04"
        assert out["phrase_params"]["n"] == 2

    def test_vietnamese_trong_n_ngay_overrides_wrong_n(self):
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 1},
            "text": "trong 3 ngày",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-05"
        assert out["phrase_params"]["n"] == 3

    def test_french_jours_overrides(self):
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 1},
            "text": "dans 5 jours",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-07"
        assert out["phrase_params"]["n"] == 5

    def test_japanese_n_nichi_overrides(self):
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 1},
            "text": "4日後",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-06"
        assert out["phrase_params"]["n"] == 4

    def test_correct_n_no_op(self):
        """When LLM already got n right, override is a no-op (same result)."""
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 2},
            "text": "within 2 days",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        assert out["iso"] == "2026-04-04"
        assert out["phrase_params"]["n"] == 2

    def test_no_n_in_text_no_override(self):
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 3},
            "text": "in a few days",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # No integer in text → LLM's n stands
        assert out["iso"] == "2026-04-05"
        assert out["phrase_params"]["n"] == 3

    def test_source_fallback_recovers_stripped_n(self):
        """LLM strips number from d_text; windowed source scan rescues."""
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 1},
            "text": "within",
        }
        source = "High priority: Steve, prepare the design document within 2 days."
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR, source)
        assert out["iso"] == "2026-04-04"
        assert out["phrase_params"]["n"] == 2

    def test_detector_does_not_fire_for_other_phrase_classes(self):
        """A '2 days' inside a named_weekday phrase must not override anything."""
        d = {
            "phrase_class": "named_weekday",
            "phrase_params": {"weekday": "friday", "offset": "this"},
            "text": "Friday — about 2 days from now",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # Should resolve as this Friday, NOT anchor+2
        assert out["iso"] == "2026-04-03"
        assert out["phrase_class"] == "named_weekday"

    def test_out_of_range_n_ignored(self):
        """Pattern bounds N to [0, 365]; absurd values are ignored."""
        d = {
            "phrase_class": "n_days",
            "phrase_params": {"n": 2},
            "text": "in 9999 days",
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, self.ANCHOR)
        # Pattern caps to 3 digits → "999"; if 999 > _MAX_FUTURE_DAYS=365
        # the detector returns None and LLM's n=2 stands.
        # (Match here finds "9999" but \d{1,3} only captures the first three.)
        assert out["phrase_params"]["n"] in (2, 999)


class TestV1ExtendedPatternsEnrichmentIntegration:
    """End-to-end: V1 extensions flow through enrich_deadline_v2_with_symbolic_iso."""

    def test_enrich_resolves_ngay_thang_when_phrase_class_missing(self):
        """LLM extracts text but omits phrase_class — V1 nth_of_month catches it."""
        anchor = date(2026, 4, 1)
        d = {
            "text": "trước ngày 10 tháng 4",
            "phrase_class": None,
            "phrase_params": None,
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-10"

    def test_enrich_resolves_cuoi_thang_when_phrase_class_missing(self):
        anchor = date(2026, 4, 1)
        d = {
            "text": "trước cuối tháng",
            "phrase_class": None,
            "phrase_params": None,
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-30"

    def test_enrich_resolves_end_of_month_when_phrase_class_missing(self):
        anchor = date(2026, 4, 1)
        d = {
            "text": "by end of month",
            "phrase_class": None,
            "phrase_params": None,
        }
        out = enrich_deadline_v2_with_symbolic_iso(d, anchor)
        assert out["iso"] == "2026-04-30"
