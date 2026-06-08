"""Phase 6.6 (recurring events, 2026-06-03): tests for the RRULE whitelist
validator + helpers in ``app.pipeline.recurrence``.

Coverage:
  - positive: each preset + custom shapes + numeric BYDAY prefix
  - negative: every reject path (FREQ/INTERVAL/BYDAY/BYMONTHDAY/UNTIL/COUNT
    bounds, mutual exclusion, unsupported props, malformed syntax)
  - canonicalisation: key order, RRULE: prefix stripping
  - next_occurrence: weekly, monthly, biweekly, exhausted COUNT, past UNTIL
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.pipeline.recurrence import (
    RecurrenceError,
    next_occurrence,
    validate_rrule,
)


# Fixed reference time for deterministic UNTIL checks.
NOW = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)


class TestValidateRruleAccepts:
    def test_daily_basic(self):
        assert validate_rrule("FREQ=DAILY", now=NOW) == "FREQ=DAILY"

    def test_weekly_byday(self):
        assert validate_rrule("FREQ=WEEKLY;BYDAY=MO,WE", now=NOW) == "FREQ=WEEKLY;BYDAY=MO,WE"

    def test_monthly_bymonthday(self):
        assert validate_rrule("FREQ=MONTHLY;BYMONTHDAY=15", now=NOW) == "FREQ=MONTHLY;BYMONTHDAY=15"

    def test_biweekly_interval(self):
        assert (
            validate_rrule("FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", now=NOW)
            == "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR"
        )

    def test_count(self):
        assert validate_rrule("FREQ=DAILY;COUNT=10", now=NOW) == "FREQ=DAILY;COUNT=10"

    def test_until_future(self):
        rule = "FREQ=WEEKLY;BYDAY=FR;UNTIL=20270801T000000Z"
        assert validate_rrule(rule, now=NOW) == rule

    def test_byday_numeric_prefix(self):
        # "2MO" = second Monday of month — valid per RFC 5545
        assert validate_rrule("FREQ=MONTHLY;BYDAY=2MO", now=NOW) == "FREQ=MONTHLY;BYDAY=2MO"

    def test_byday_negative_prefix(self):
        # "-1FR" = last Friday of month
        assert validate_rrule("FREQ=MONTHLY;BYDAY=-1FR", now=NOW) == "FREQ=MONTHLY;BYDAY=-1FR"

    def test_strips_rrule_prefix(self):
        assert validate_rrule("RRULE:FREQ=DAILY", now=NOW) == "FREQ=DAILY"

    def test_canonical_key_order(self):
        # Input shuffled; canonical output reorders to FREQ→INTERVAL→BYDAY→...
        rule = "BYDAY=MO;INTERVAL=2;FREQ=WEEKLY"
        assert validate_rrule(rule, now=NOW) == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"

    def test_case_insensitive_keys(self):
        assert validate_rrule("freq=weekly;byday=mo", now=NOW) == "FREQ=WEEKLY;BYDAY=MO"


class TestValidateRruleRejects:
    def test_empty(self):
        with pytest.raises(RecurrenceError, match="non-empty"):
            validate_rrule("", now=NOW)

    def test_none_type(self):
        with pytest.raises(RecurrenceError):
            validate_rrule(None, now=NOW)  # type: ignore[arg-type]

    def test_missing_freq(self):
        with pytest.raises(RecurrenceError, match="FREQ is required"):
            validate_rrule("INTERVAL=2", now=NOW)

    def test_invalid_freq(self):
        with pytest.raises(RecurrenceError, match="FREQ must be one of"):
            validate_rrule("FREQ=HOURLY", now=NOW)

    def test_interval_too_high(self):
        with pytest.raises(RecurrenceError, match="INTERVAL must be 1..365"):
            validate_rrule("FREQ=DAILY;INTERVAL=10000", now=NOW)

    def test_interval_zero(self):
        with pytest.raises(RecurrenceError, match="INTERVAL must be 1..365"):
            validate_rrule("FREQ=DAILY;INTERVAL=0", now=NOW)

    def test_byday_invalid_weekday(self):
        with pytest.raises(RecurrenceError, match="BYDAY weekday"):
            validate_rrule("FREQ=WEEKLY;BYDAY=XX", now=NOW)

    def test_byday_zero_prefix(self):
        with pytest.raises(RecurrenceError, match="out of range"):
            validate_rrule("FREQ=WEEKLY;BYDAY=0MO", now=NOW)

    def test_bymonthday_out_of_range(self):
        with pytest.raises(RecurrenceError, match="BYMONTHDAY must be 1..31"):
            validate_rrule("FREQ=MONTHLY;BYMONTHDAY=32", now=NOW)

    def test_count_too_high(self):
        with pytest.raises(RecurrenceError, match="COUNT must be 1..520"):
            validate_rrule("FREQ=WEEKLY;COUNT=99999", now=NOW)

    def test_until_past(self):
        with pytest.raises(RecurrenceError, match="must be in the future"):
            validate_rrule("FREQ=WEEKLY;UNTIL=20200101T000000Z", now=NOW)

    def test_until_no_z(self):
        with pytest.raises(RecurrenceError, match="UTC"):
            validate_rrule("FREQ=WEEKLY;UNTIL=20270101T000000", now=NOW)

    def test_until_malformed(self):
        with pytest.raises(RecurrenceError, match="malformed UNTIL"):
            validate_rrule("FREQ=WEEKLY;UNTIL=garbageZ", now=NOW)

    def test_count_and_until_mutually_exclusive(self):
        with pytest.raises(RecurrenceError, match="mutually exclusive"):
            validate_rrule(
                "FREQ=WEEKLY;UNTIL=20270101T000000Z;COUNT=10", now=NOW
            )

    def test_rejects_byhour(self):
        with pytest.raises(RecurrenceError, match="unsupported"):
            validate_rrule("FREQ=WEEKLY;BYHOUR=9", now=NOW)

    def test_rejects_byminute(self):
        with pytest.raises(RecurrenceError, match="unsupported"):
            validate_rrule("FREQ=DAILY;BYMINUTE=30", now=NOW)

    def test_rejects_bysetpos(self):
        with pytest.raises(RecurrenceError, match="unsupported"):
            validate_rrule("FREQ=MONTHLY;BYDAY=FR;BYSETPOS=-1", now=NOW)

    def test_rejects_wkst(self):
        with pytest.raises(RecurrenceError, match="unsupported"):
            validate_rrule("FREQ=WEEKLY;WKST=MO", now=NOW)

    def test_malformed_segment(self):
        with pytest.raises(RecurrenceError, match="malformed"):
            validate_rrule("NOTANRRULE", now=NOW)

    def test_duplicate_key(self):
        with pytest.raises(RecurrenceError, match="duplicate"):
            validate_rrule("FREQ=DAILY;FREQ=WEEKLY", now=NOW)

    def test_empty_value(self):
        with pytest.raises(RecurrenceError, match="empty key or value"):
            validate_rrule("FREQ=", now=NOW)


class TestNextOccurrence:
    def test_weekly_monday(self):
        # Anchor 2026-01-05 (Mon). After 2026-06-03 → next Monday 2026-06-08.
        assert next_occurrence("FREQ=WEEKLY;BYDAY=MO", date(2026, 1, 5), after=date(2026, 6, 3)) == date(2026, 6, 8)

    def test_biweekly_friday(self):
        # Anchor 2026-05-29 (Fri). Biweekly → next is 2026-06-12 after 2026-06-03.
        assert next_occurrence("FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", date(2026, 5, 29), after=date(2026, 6, 3)) == date(2026, 6, 12)

    def test_monthly_15th(self):
        # Anchor 2026-01-15. After 2026-06-03 → 2026-06-15.
        assert next_occurrence("FREQ=MONTHLY;BYMONTHDAY=15", date(2026, 1, 15), after=date(2026, 6, 3)) == date(2026, 6, 15)

    def test_after_inclusive(self):
        # When after == an occurrence date, return that date (inc=True).
        assert next_occurrence("FREQ=DAILY", date(2026, 1, 1), after=date(2026, 6, 4)) == date(2026, 6, 4)

    def test_exhausted_count(self):
        # COUNT=5 starting 2026-01-01 → 5 daily occurrences, last 2026-01-05.
        # Asking for next after 2026-06-04 → None.
        assert next_occurrence("FREQ=DAILY;COUNT=5", date(2026, 1, 1), after=date(2026, 6, 4)) is None

    def test_malformed_returns_none(self):
        # Defensive: caller must not crash on garbage input.
        assert next_occurrence("garbage", date(2026, 1, 1)) is None

    def test_strips_rrule_prefix(self):
        assert next_occurrence("RRULE:FREQ=DAILY", date(2026, 1, 1), after=date(2026, 6, 4)) == date(2026, 6, 4)
