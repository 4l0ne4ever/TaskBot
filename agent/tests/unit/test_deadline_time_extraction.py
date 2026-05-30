"""Round 13 (2026-05-31): unit tests for the time-of-day extractor and the
normalize-tasks integration.

The LLM already emits the verbatim deadline phrase in
``deadline_v2.text`` / ``deadline_v2.resolved_from`` ("Friday, 20 June
2026, 3:00 PM ICT", "trước 17:00 ngày 12/06/2026", "by 9 AM", "EOD",
etc.). ``_extract_time_of_day`` deterministically pulls an HH:MM out of
that text — no extra LLM call. ``_normalize_task`` then carries the
``datetime.time`` (or None) on each output task under the new
``deadline_time`` key.
"""
from __future__ import annotations

from datetime import time

import pytest

from app.pipeline.nodes.normalize_tasks import (
    _extract_time_of_day,
    normalize_tasks,
)


@pytest.mark.parametrize("text,expected", [
    # English with explicit minutes
    ("Friday, 20 June 2026, 3:00 PM ICT", time(15, 0)),
    ("by 9:30 AM Friday", time(9, 30)),
    ("Please submit by 11:45 PM tonight", time(23, 45)),
    # English bare hour with AM/PM
    ("submit by 5 PM", time(17, 0)),
    ("call at 9 AM", time(9, 0)),
    ("send by noon (12 PM)", time(12, 0)),
    ("by midnight (12 AM)", time(0, 0)),
    # 24-hour format (VN, military)
    ("trước 17:00 ngày 12/06/2026", time(17, 0)),
    ("Hạn: 22/06/2026, 10:00 sáng", time(10, 0)),
    ("dispatch at 23:59", time(23, 59)),
    # No time present — None
    ("Friday, 20 June 2026", None),
    ("by end of week", None),
    ("trước thứ Sáu", None),
    # Edge: invalid hour/minute is rejected
    ("at 25:00", None),
    ("at 12:67", None),
    # Edge: must look like a clock — bare numbers don't trip the parser
    ("June 20", None),
    ("project v3.2", None),
])
def test_extract_time_of_day_parametric(text, expected):
    assert _extract_time_of_day(text) == expected


def test_extract_time_of_day_handles_none_and_empty():
    assert _extract_time_of_day(None) is None
    assert _extract_time_of_day("") is None
    assert _extract_time_of_day("   ") is None


def test_extract_time_of_day_picks_first_match():
    """Most phrases carry one time; if two are present (rare) the first
    wins so the parser is deterministic and easy to reason about."""
    assert _extract_time_of_day("from 9 AM to 5 PM") == time(9, 0)


def test_normalize_task_populates_deadline_time_from_deadline_v2_text():
    """End-to-end through the node: an LLM output with a time string in
    deadline_v2.text lands on the normalized task as a datetime.time."""
    result = normalize_tasks({
        "extracted_tasks": [
            {
                "title": "Prepare slides",
                "assignee": "Emily",
                "deadline_v2": {
                    "type": "exact",
                    "iso": "2026-06-20",
                    "text": "Friday, 20 June 2026, 3:00 PM ICT",
                    "resolved_from": "Friday, 20 June 2026, 3:00 PM ICT",
                    "confidence": 0.95,
                    "source": "llm",
                    "is_ambiguous": False,
                    "phrase_class": "absolute",
                },
                "confidence": 0.92,
            }
        ],
        "errors": [],
    })
    assert len(result["normalized_tasks"]) == 1
    t = result["normalized_tasks"][0]
    assert t["deadline"] == "2026-06-20"
    assert t["deadline_time"] == time(15, 0)


def test_normalize_task_deadline_time_falls_back_to_resolved_from_when_text_empty():
    """deadline_v2.text can be missing; resolved_from is the same phrase in
    that case (per _coerce_deadline_v2's backfill rules), so the time
    parser must look at both."""
    result = normalize_tasks({
        "extracted_tasks": [
            {
                "title": "Vendor review",
                "deadline_v2": {
                    "type": "exact",
                    "iso": "2026-06-16",
                    "text": None,
                    "resolved_from": "trước 09:00 ngày 16/06/2026",
                    "confidence": 0.9,
                    "source": "llm",
                    "phrase_class": "absolute",
                },
                "confidence": 0.9,
            }
        ],
        "errors": [],
    })
    t = result["normalized_tasks"][0]
    assert t["deadline_time"] == time(9, 0)


def test_normalize_task_deadline_time_is_none_when_no_time_in_phrase():
    """Round 13's promise: when the source says nothing about time, the
    field is None and the UI renders date-only — pre-Round-13 behaviour
    preserved exactly."""
    result = normalize_tasks({
        "extracted_tasks": [
            {
                "title": "Some task",
                "deadline_v2": {
                    "type": "exact",
                    "iso": "2026-06-20",
                    "text": "Friday, 20 June 2026",
                    "resolved_from": "Friday, 20 June 2026",
                    "confidence": 0.95,
                    "source": "llm",
                    "phrase_class": "absolute",
                },
                "confidence": 0.9,
            }
        ],
        "errors": [],
    })
    t = result["normalized_tasks"][0]
    assert t["deadline_time"] is None


def test_normalize_task_keeps_deadline_time_none_when_no_deadline_at_all():
    """A task with no deadline_v2 (graceful-degradation path) still has the
    deadline_time field on the output dict — just with None — so downstream
    consumers don't see a KeyError."""
    result = normalize_tasks({
        "extracted_tasks": [
            {"title": "Action without deadline", "assignee": "Emily"}
        ],
        "errors": [],
    })
    t = result["normalized_tasks"][0]
    assert "deadline_time" in t
    assert t["deadline_time"] is None
