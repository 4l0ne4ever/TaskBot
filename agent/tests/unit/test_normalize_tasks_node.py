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


def test_normalize_tasks_rejects_incomplete_schema() -> None:
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


def test_normalize_tasks_still_rejects_invalid_confidence() -> None:
    """Unsalvageable inputs must still be rejected. Confidence outside [0,1]
    is a hard schema violation we cannot safely coerce."""
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
    assert result["normalized_tasks"] == []


def test_normalize_tasks_still_rejects_unparseable_iso() -> None:
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
    assert result["normalized_tasks"] == []
