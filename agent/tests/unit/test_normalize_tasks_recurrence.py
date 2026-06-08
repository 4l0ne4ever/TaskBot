"""Phase 6.6 (recurring events, 2026-06-03): tests for normalize_tasks
routing of LLM-emitted ``recurrence_rule`` → validated
``recurrence_suggested`` on the task dict.

normalize_tasks must:
  - pass a whitelist-valid RRULE through (canonicalised) as recurrence_suggested
  - drop a malformed RRULE silently (graceful degradation — title is still valid)
  - emit recurrence_suggested=None when the LLM doesn't emit the field
  - never populate recurrence_rule (active rule = user-confirm only)
"""
from __future__ import annotations

from app.pipeline.nodes.normalize_tasks import normalize_tasks


def _minimal_state(extracted_tasks):
    return {
        "extracted_tasks": extracted_tasks,
        "errors": [],
        "metadata": {"sent_at": "2026-06-04"},
        "cleaned_text": "sample",
        "user_id": "u-1",
    }


def _make_task(**extras):
    base = {
        "title": "Submit report",
        "description": None,
        "assignee": "Anna",
        "source_ref": None,
        "deadline_v2": {
            "type": "exact",
            "iso": "2026-06-15",
            "start": None,
            "end": None,
            "text": "by 2026-06-15",
            "resolved_from": "by 2026-06-15",
            "confidence": 0.9,
            "source": "llm",
            "is_ambiguous": False,
        },
        "confidence": 0.9,
    }
    base.update(extras)
    return base


def test_valid_recurrence_rule_routes_to_suggested():
    state = _minimal_state([_make_task(recurrence_rule="FREQ=WEEKLY;BYDAY=MO")])
    out = normalize_tasks(state)
    tasks = out["normalized_tasks"]
    assert len(tasks) == 1
    assert tasks[0]["recurrence_suggested"] == "FREQ=WEEKLY;BYDAY=MO"
    # Active rule is NEVER set by normalize — that requires explicit user
    # apply via the backend PATCH endpoint.
    assert "recurrence_rule" not in tasks[0]


def test_malformed_recurrence_dropped_silently():
    # Garbage RRULE must not reject the whole task — title is still valid.
    state = _minimal_state([_make_task(recurrence_rule="garbage;FREQ=INVALID")])
    out = normalize_tasks(state)
    assert len(out["normalized_tasks"]) == 1
    assert out["normalized_tasks"][0]["recurrence_suggested"] is None


def test_unsupported_property_dropped():
    # BYHOUR is outside whitelist — drop, don't reject task.
    state = _minimal_state([_make_task(recurrence_rule="FREQ=WEEKLY;BYHOUR=9")])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] is None


def test_missing_recurrence_field():
    state = _minimal_state([_make_task()])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] is None


def test_canonicalises_shuffled_keys():
    # LLM emits keys in unexpected order; normalize should canonicalise.
    state = _minimal_state([_make_task(recurrence_rule="BYDAY=MO;FREQ=WEEKLY;INTERVAL=2")])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"


def test_empty_string_recurrence_dropped():
    state = _minimal_state([_make_task(recurrence_rule="")])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] is None


def test_non_string_recurrence_dropped():
    state = _minimal_state([_make_task(recurrence_rule=123)])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] is None


def test_monthly_bymonthday_passes():
    state = _minimal_state([_make_task(recurrence_rule="FREQ=MONTHLY;BYMONTHDAY=15")])
    out = normalize_tasks(state)
    assert out["normalized_tasks"][0]["recurrence_suggested"] == "FREQ=MONTHLY;BYMONTHDAY=15"
