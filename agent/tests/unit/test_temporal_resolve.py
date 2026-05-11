"""Unit tests for symbolic deadline resolution (anchor + closed-set phrase)."""
from __future__ import annotations

from datetime import date

from app.pipeline.temporal_resolve import (
    enrich_deadline_v2_with_symbolic_iso,
    parse_anchor_date,
    try_resolve_deadline_iso,
)


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
