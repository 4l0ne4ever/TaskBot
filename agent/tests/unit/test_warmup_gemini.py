"""warmup_gemini_connection is best-effort and must not raise when Gemini is off."""

from __future__ import annotations

import pytest

from app.pipeline import llm as llm_module


def test_warmup_noop_without_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_module.settings, "gemini_api_key", None)
    llm_module.warmup_gemini_connection()


def test_warmup_noop_with_empty_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_module.settings, "gemini_api_key", "   ")
    llm_module.warmup_gemini_connection()
