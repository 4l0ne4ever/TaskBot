"""Eval-only assignee normalization (Q-05).

The bridge must not enumerate address words. It removes only address-marker
punctuation; semantic matching is delegated to the data-shape resolver score.
"""
from __future__ import annotations

from metrics import _canonical_assignee_for_eval


def test_preserves_address_words_without_a_list():
    assert _canonical_assignee_for_eval("Bạn Hương") == "bạn hương"
    assert _canonical_assignee_for_eval("Anh Tuấn") == "anh tuấn"


def test_at_mention_marker_is_removed():
    assert _canonical_assignee_for_eval("@Anh Tuấn") == "anh tuấn"


def test_non_rubric_honorifics_are_left_untouched():
    """Address-like words must not be stripped here.

    Matching is handled by score_names/token containment, avoiding a widening
    word list in eval.
    """
    assert _canonical_assignee_for_eval("Cô Hương") == "cô hương"
    assert _canonical_assignee_for_eval("Thầy Nam") == "thầy nam"
    assert _canonical_assignee_for_eval("Dr. Smith") == "dr. smith"
