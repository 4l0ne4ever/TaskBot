from app.pipeline.nodes.normalize_tasks import normalize_tasks


def test_normalize_tasks_passes_evidence_quote_when_set() -> None:
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Submit report",
                    "assignee": "Bob",
                    "evidence_quote": "Submit report by Friday",
                    "deadline_v2": {
                        "type": "exact",
                        "iso": "2026-04-05",
                        "start": None,
                        "end": None,
                        "text": "by Friday",
                        "resolved_from": "by Friday",
                        "confidence": 0.89,
                        "source": "llm",
                        "is_ambiguous": False,
                    },
                    "priority": "high",
                    "confidence": 0.92,
                    "uncertainty": None,
                }
            ],
            "errors": [],
        }
    )
    assert result["normalized_tasks"][0].get("evidence_quote") == "Submit report by Friday"


def test_normalize_tasks_accepts_schema_complete_task() -> None:
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Submit report",
                    "description": "Submit to hiring panel",
                    "assignee": "Bob",
                    "source_ref": "email-1",
                    "deadline_v2": {
                        "type": "exact",
                        "iso": "2026-04-05",
                        "start": None,
                        "end": None,
                        "text": "by Friday",
                        "resolved_from": "by Friday",
                        "confidence": 0.89,
                        "source": "llm",
                        "is_ambiguous": False,
                    },
                    "priority": "high",
                    "confidence": 0.92,
                    "uncertainty": None,
                }
            ],
            "errors": [],
        }
    )
    assert result["normalized_tasks"][0]["deadline"] == "2026-04-05"
    assert result["normalized_tasks"][0]["confidence"] == 0.92
    assert result["normalized_tasks"][0]["deadline_v2"]["source"] == "llm"
    assert result["normalized_tasks"][0]["source_ref"] == "email-1"
    assert result["errors"] == []


def test_normalize_tasks_strips_title_suffix_when_matches_deadline_v2_text() -> None:
    phrase = "trước thứ Sáu"
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": f"báo cáo tháng 3 {phrase}",
                    "assignee": "A",
                    "deadline_v2": {
                        "type": "exact",
                        "iso": "2026-04-03",
                        "start": None,
                        "end": None,
                        "text": phrase,
                        "resolved_from": phrase,
                        "confidence": 0.85,
                        "source": "llm",
                        "is_ambiguous": False,
                    },
                    "priority": None,
                    "confidence": 0.9,
                    "uncertainty": None,
                }
            ],
            "errors": [],
        }
    )
    assert result["normalized_tasks"][0]["title"] == "báo cáo tháng 3"


def test_normalize_tasks_maps_relative_with_resolved_iso_to_deadline() -> None:
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Finish draft",
                    "assignee": "Ann",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": "2026-04-10",
                        "start": None,
                        "end": None,
                        "text": "before Friday",
                        "resolved_from": "before Friday",
                        "confidence": 0.8,
                        "source": "llm",
                        "is_ambiguous": False,
                    },
                    "priority": None,
                    "confidence": 0.85,
                    "uncertainty": None,
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    assert result["normalized_tasks"][0]["deadline"] == "2026-04-10"


def test_normalize_tasks_keeps_task_when_deadline_v2_missing() -> None:
    """Graceful degradation (real-world dogfooding finding, 2026-05-26): when the
    LLM omits ``deadline_v2`` entirely, a task with a valid title must NOT be
    dropped — it is kept with ``deadline=None`` and a canonical ``type="none"``
    so it surfaces as a pending item flagged "Missing: deadline". The previous
    behaviour silently discarded the whole task, amplifying a single field-level
    LLM omission into total task loss."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Do work",
                    "assignee": "Alice",
                    "priority": "high",
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    t = result["normalized_tasks"][0]
    assert t["title"] == "Do work"
    assert t["assignee"] == "Alice"
    assert t["deadline"] is None
    assert t["deadline_v2"]["type"] == "none"
    assert t["deadline_v2"]["iso"] is None


def test_normalize_tasks_still_drops_task_with_invalid_title() -> None:
    """The title guardrail is unchanged: a task with no usable title is
    meaningless and must still be dropped (with an error logged). Graceful
    degradation rescues missing *deadlines*, not missing *titles*."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "   ",
                    "assignee": "Alice",
                    "deadline_v2": {"iso": "2026-04-03", "confidence": 0.9, "source": "llm"},
                    "confidence": 0.9,
                }
            ],
            "errors": [],
        }
    )
    assert result["normalized_tasks"] == []
    assert result["errors"]


def test_normalize_tasks_coerces_non_llm_source_to_llm() -> None:
    """Postel's-law coercion: the only emitter of ``deadline_v2`` in the
    pipeline is the LLM node, so an unexpected ``source`` value is coerced
    to ``"llm"`` instead of dropping the entire task. The strict guard used
    to do the opposite and caused silent data loss in production traces."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Send docs",
                    "assignee": "Ann",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": None,
                        "start": None,
                        "end": None,
                        "text": "ASAP",
                        "resolved_from": "ASAP",
                        "confidence": 0.4,
                        "source": "fallback",
                        "is_ambiguous": True,
                    },
                    "priority": "high",
                    "confidence": 0.4,
                    "uncertainty": {"type": "ambiguous", "reason": "relative urgency"},
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    assert result["normalized_tasks"][0]["deadline_v2"]["source"] == "llm"


def test_normalize_tasks_coerces_partial_deadline_v2_from_llm() -> None:
    """Regression for 2026-04-18 forensic finding: on real sweep traces the
    LLM sometimes omits ``type``/``text``/``start``/``end`` from
    ``deadline_v2`` and only returns ``iso``/``confidence``/``resolved_from``/
    ``source``/``is_ambiguous``. The previous strict guard dropped all such
    tasks silently. The coerced schema must infer ``type`` from ``iso`` and
    backfill ``text`` from ``resolved_from``."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "báo cáo tháng 3",
                    "assignee": "Đặng Tuấn Kiệt",
                    "deadline_v2": {
                        "iso": "2026-04-03",
                        "resolved_from": "trước thứ Sáu",
                        "source": "llm",
                        "is_ambiguous": False,
                        "confidence": 0.9,
                    },
                    "confidence": 0.9,
                }
            ],
            "errors": [],
            "metadata": {"sent_at": "2026-04-02"},
        }
    )
    assert len(result["normalized_tasks"]) == 1
    t = result["normalized_tasks"][0]
    assert t["deadline"] == "2026-04-03"
    assert t["deadline_v2"]["type"] == "exact"
    assert t["deadline_v2"]["text"] == "trước thứ Sáu"
    assert t["deadline_v2"]["start"] is None
    assert t["deadline_v2"]["end"] is None


def test_normalize_tasks_discards_unsalvageable_deadline_but_keeps_task() -> None:
    """An unsalvageable deadline (confidence outside [0,1]) is still NOT trusted —
    but under graceful degradation the bad deadline is discarded (``deadline=None``,
    ``type="none"``) rather than throwing away the whole valid-title task."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Finish task",
                    "deadline_v2": {
                        "iso": "2026-04-03",
                        "confidence": 1.5,
                        "source": "llm",
                    },
                    "confidence": 0.9,
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    t = result["normalized_tasks"][0]
    assert t["title"] == "Finish task"
    assert t["deadline"] is None
    assert t["deadline_v2"]["type"] == "none"


def test_normalize_tasks_discards_unparseable_iso_but_keeps_task() -> None:
    """Same contract for an unparseable ``iso``: the bad date is dropped, the
    valid-title task survives as a pending item with no deadline."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Finish task",
                    "deadline_v2": {
                        "iso": "next Friday",
                        "confidence": 0.9,
                        "source": "llm",
                    },
                    "confidence": 0.9,
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    t = result["normalized_tasks"][0]
    assert t["title"] == "Finish task"
    assert t["deadline"] is None
    assert t["deadline_v2"]["type"] == "none"


def test_normalize_tasks_passes_week_offset_through_coercion() -> None:
    """week_offset from the LLM must survive _coerce_deadline_v2 so the
    temporal_resolve module can apply the correct arithmetic (Q-01 / D.2)."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Review Q1 report",
                    "assignee": "Hoàng",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": None,
                        "start": None,
                        "end": None,
                        "text": "thứ Sáu tới",
                        "resolved_from": "thứ Sáu tới",
                        "confidence": 0.88,
                        "source": "llm",
                        "is_ambiguous": False,
                        "week_offset": "next",
                    },
                    "confidence": 0.88,
                }
            ],
            "errors": [],
            "metadata": {"sent_at": "2026-04-08"},
        }
    )
    assert len(result["normalized_tasks"]) == 1
    dv2 = result["normalized_tasks"][0]["deadline_v2"]
    assert dv2["week_offset"] == "next"
    # Anchor 2026-04-08 (Wed); nearest Friday = 2026-04-10; +7 = 2026-04-17
    assert result["normalized_tasks"][0]["deadline"] == "2026-04-17"


def test_normalize_tasks_passes_phrase_class_and_params_through_coercion() -> None:
    """phrase_class and phrase_params must survive _coerce_deadline_v2 and
    reach the V2 resolver so it can compute the correct date.

    Root cause of 2026-05-13 regression: _coerce_deadline_v2 was written
    before V2 neuro-symbolic fields were introduced.  It silently dropped them,
    so enrich_deadline_v2_with_symbolic_iso never entered the V2 path even
    when the LLM output phrase_class/phrase_params correctly.
    """
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "hoàn thành bản đánh giá nhân sự",
                    "assignee": "Nguyễn",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": None,
                        "start": None,
                        "end": None,
                        "text": "thứ Sáu tới",
                        "resolved_from": "thứ Sáu tới",
                        "confidence": 0.88,
                        "source": "llm",
                        "is_ambiguous": False,
                        "week_offset": None,
                        "phrase_class": "named_weekday",
                        "phrase_params": {"weekday": "friday", "offset": "next"},
                    },
                    "confidence": 0.88,
                }
            ],
            "errors": [],
            "metadata": {"sent_at": "2026-04-02"},  # Thursday
        }
    )
    assert len(result["normalized_tasks"]) == 1
    task = result["normalized_tasks"][0]
    dv2 = task["deadline_v2"]
    assert dv2["phrase_class"] == "named_weekday"
    assert dv2["phrase_params"] == {"weekday": "friday", "offset": "next"}
    # Anchor 2026-04-02 (Thu); this Friday = 2026-04-03; +7 (next) = 2026-04-10
    assert task["deadline"] == "2026-04-10"


def test_normalize_tasks_v2_fallback_to_v1_when_phrase_params_invalid() -> None:
    """When phrase_class is present but phrase_params is missing, the resolver
    must fall through to V1 text-pattern rescue instead of returning iso=None.

    This handles partial LLM output where phrase_class was set but the
    phrase_params object is absent or structurally wrong.
    """
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Finish report",
                    "assignee": "Lan",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": None,
                        "text": "tomorrow",
                        "resolved_from": "tomorrow",
                        "confidence": 0.88,
                        "source": "llm",
                        "is_ambiguous": False,
                        "phrase_class": "named_weekday",  # wrong class for "tomorrow"
                        "phrase_params": None,             # params missing
                    },
                    "confidence": 0.88,
                }
            ],
            "errors": [],
            "metadata": {"sent_at": "2026-04-02"},
        }
    )
    assert len(result["normalized_tasks"]) == 1
    task = result["normalized_tasks"][0]
    # V2 fails (named_weekday + no params), V1 rescues via "tomorrow" in text
    assert task["deadline"] == "2026-04-03"


def test_normalize_tasks_coerces_invalid_week_offset_to_unknown() -> None:
    """An unexpected string from the LLM is coerced to 'unknown' rather than
    rejecting the whole task (Postel's principle)."""
    result = normalize_tasks(
        {
            "extracted_tasks": [
                {
                    "title": "Send slides",
                    "assignee": "An",
                    "deadline_v2": {
                        "type": "relative",
                        "iso": "2026-04-10",
                        "start": None,
                        "end": None,
                        "text": "thứ Sáu",
                        "resolved_from": "thứ Sáu",
                        "confidence": 0.85,
                        "source": "llm",
                        "is_ambiguous": False,
                        "week_offset": "definitely_invalid_value",
                    },
                    "confidence": 0.85,
                }
            ],
            "errors": [],
        }
    )
    assert len(result["normalized_tasks"]) == 1
    assert result["normalized_tasks"][0]["deadline_v2"]["week_offset"] == "unknown"
