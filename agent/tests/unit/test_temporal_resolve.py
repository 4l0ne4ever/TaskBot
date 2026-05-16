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


def test_open_ended_phrases_are_not_resolved():
    """Closed-set policy: phrases like 'cuối tuần' / 'end of quarter' must not be guessed here."""
    anchor = date(2026, 4, 6)
    assert try_resolve_deadline_iso({"text": "deadline cuối tuần"}, anchor) is None
    assert try_resolve_deadline_iso({"text": "end of the week"}, anchor) is None
    assert try_resolve_deadline_iso({"text": "early next week"}, anchor) is None
    assert try_resolve_deadline_iso({"text": "end of quarter"}, anchor) is None


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
