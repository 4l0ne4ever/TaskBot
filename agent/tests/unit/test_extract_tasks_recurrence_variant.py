"""Phase 6.6 (recurring events, 2026-06-03): tests for the
extract_tasks variant routing flag + prompt assembly.

Covers:
  - default behaviour: variant ON (post eval-gate flip 2026-06-05)
  - opt-out via TASKBOT_EXTRACTION_VARIANT=v1
  - sent-folder mail always uses SENT prompt (variant skipped even when on)
  - parse_extraction_response passes recurrence_rule through unchanged
  - merge preserves recurrence_rule across duplicate-merge collisions
"""
from __future__ import annotations

import os

import pytest

from app.pipeline.nodes.extract_tasks import (
    _build_extraction_prompt,
    _merge_task_items,
    _recurrence_variant_enabled,
    parse_extraction_response,
)


@pytest.fixture(autouse=True)
def _clear_variant_env():
    saved = os.environ.pop("TASKBOT_EXTRACTION_VARIANT", None)
    yield
    if saved is not None:
        os.environ["TASKBOT_EXTRACTION_VARIANT"] = saved


# ── variant flag ──────────────────────────────────────────────────────────


def test_variant_default_on():
    assert _recurrence_variant_enabled() is True


def test_variant_v1_opt_out():
    os.environ["TASKBOT_EXTRACTION_VARIANT"] = "v1"
    assert _recurrence_variant_enabled() is False


def test_variant_explicit_recurrence_on():
    os.environ["TASKBOT_EXTRACTION_VARIANT"] = "recurrence"
    assert _recurrence_variant_enabled() is True


# ── prompt assembly ───────────────────────────────────────────────────────


def _state(folder=None):
    md = {"sender": "a@b", "sent_at": "2026-06-04", "subject": "x"}
    if folder:
        md["folder"] = folder
    return {"metadata": md, "source_type": "gmail"}


def test_default_prompt_contains_recurrence_section():
    sys_prompt, user_prompt = _build_extraction_prompt(_state(), "sample text")
    assert "recurrence_rule" in sys_prompt.lower()
    assert "rrule" in user_prompt.lower()


def test_v1_prompt_omits_recurrence_section():
    os.environ["TASKBOT_EXTRACTION_VARIANT"] = "v1"
    sys_prompt, user_prompt = _build_extraction_prompt(_state(), "sample text")
    assert "recurrence_rule" not in sys_prompt.lower()
    assert "rrule" not in user_prompt.lower()


def test_sent_folder_always_uses_sent_prompt():
    # variant ON but folder=sent → sent prompt, no recurrence section
    sys_prompt, user_prompt = _build_extraction_prompt(_state(folder="sent"), "sample text")
    assert "sent by the current user" in sys_prompt.lower()
    assert "rrule" not in user_prompt.lower()


def test_recurrence_section_placed_before_text_block():
    sys_prompt, user_prompt = _build_extraction_prompt(_state(), "sample text")
    # Order matters — the LLM otherwise treats post-JSON-closer text as
    # auxiliary commentary and ignores the directive (confirmed in dogfood
    # 2026-06-04). Position is the gate against that regression.
    idx_rules = user_prompt.lower().find("rrule")
    idx_text = user_prompt.find("Text (source data")
    assert idx_rules >= 0 and idx_text >= 0
    assert idx_rules < idx_text, "recurrence rules must precede the Text block"


# ── parse_extraction_response: recurrence_rule passthrough ────────────────


def test_parse_passes_recurrence_through():
    raw = """{"tasks":[{"title":"Report","recurrence_rule":"FREQ=WEEKLY;BYDAY=FR"}]}"""
    items = parse_extraction_response(raw)
    assert len(items) == 1
    assert items[0]["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=FR"


def test_parse_recurrence_none_when_missing():
    raw = """{"tasks":[{"title":"Report"}]}"""
    items = parse_extraction_response(raw)
    assert items[0]["recurrence_rule"] is None


def test_parse_recurrence_non_string_normalised_to_none():
    # LLM could emit number/null — must not propagate a non-string.
    raw = """{"tasks":[{"title":"Report","recurrence_rule":42}]}"""
    items = parse_extraction_response(raw)
    assert items[0]["recurrence_rule"] is None


def test_parse_recurrence_empty_string_normalised_to_none():
    raw = """{"tasks":[{"title":"Report","recurrence_rule":""}]}"""
    items = parse_extraction_response(raw)
    assert items[0]["recurrence_rule"] is None


# ── merge: recurrence preserved on dedupe ────────────────────────────────


def test_merge_preserves_recurrence_from_incoming():
    base = {"title": "Report", "recurrence_rule": None}
    incoming = {"title": "Report", "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"}
    merged = _merge_task_items(base, incoming)
    assert merged["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO"


def test_merge_does_not_overwrite_existing_recurrence():
    base = {"title": "Report", "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"}
    incoming = {"title": "Report", "recurrence_rule": "FREQ=DAILY"}
    merged = _merge_task_items(base, incoming)
    # First-write-wins like other dedup fields. The user can edit later.
    assert merged["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO"
