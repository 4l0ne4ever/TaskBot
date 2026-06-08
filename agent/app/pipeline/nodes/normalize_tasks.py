import re
from datetime import date, time

from app.pipeline.recurrence import RecurrenceError, validate_rrule
from app.pipeline.state import PipelineState
from app.pipeline.temporal_resolve import enrich_deadline_v2_with_symbolic_iso, parse_anchor_date
from app.services.assignee_resolver import AssigneeResolver, get_default_resolver


# Round 13 (2026-05-31) — pull a time-of-day out of the LLM's verbatim
# deadline phrase (deadline_v2.text). The LLM already extracts the full
# textual deadline ("Friday, 20 June 2026, 3:00 PM ICT", "trước 17:00 ngày
# 12/06/2026", "by 9 AM", etc.) but never had a slot to put the time in.
# Parser is deterministic, no LLM call. Matches:
#   "3:00 PM"   → 15:00
#   "3 PM"      → 15:00
#   "15:00"     → 15:00
#   "9 AM"      → 09:00
#   "09:30"     → 09:30
# Ignores 2-digit numbers that aren't valid times (00-23 hours, 00-59 mins).
# Picks the FIRST match — most deadline phrases carry one time at most.
_TIME_PATTERNS = (
    # H:MM or HH:MM with optional AM/PM (greedy on AM/PM so "9:00 AM" beats "9:00")
    re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b", re.IGNORECASE),
    # H AM/PM (no minutes) — e.g. "by 5 PM"
    re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.IGNORECASE),
    # 24-hour HH:MM without AM/PM — e.g. "17:00", VN "trước 9:30 ngày..."
    re.compile(r"\b(\d{1,2}):(\d{2})\b"),
)


def _extract_time_of_day(text: str | None) -> time | None:
    """Best-effort extract HH:MM from the LLM's deadline_v2.text phrase.

    Returns ``None`` when no plausible time is found — date-only behaviour
    is preserved exactly for every existing emit.
    """
    if not text or not isinstance(text, str):
        return None
    low = text.lower()
    for pattern in _TIME_PATTERNS:
        m = pattern.search(low)
        if not m:
            continue
        groups = m.groups()
        hour = int(groups[0])
        minute = int(groups[1]) if len(groups) >= 2 and groups[1] and groups[1].isdigit() else 0
        meridiem = ""
        # Find AM/PM in the matched groups (it's the last one for the
        # first two patterns, absent for the 24-hour pattern).
        for g in groups:
            if isinstance(g, str) and g.lower() in ("am", "pm"):
                meridiem = g.lower()
                break
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        try:
            return time(hour=hour, minute=minute)
        except ValueError:
            continue
    return None

CANONICAL_DEADLINE_KEYS = (
    "type",
    "iso",
    "start",
    "end",
    "text",
    "resolved_from",
    "confidence",
    "source",
    "is_ambiguous",
    "week_offset",
    "phrase_class",
    "phrase_params",
)
_VALID_DEADLINE_TYPES = ("exact", "range", "relative", "none")
_VALID_WEEK_OFFSETS = ("this", "next", "after_next", "unknown")


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _coerce_deadline_v2(d: object) -> dict | None:
    """Turn a partial deadline_v2 from the LLM into the canonical schema shape.

    Motivation (forensic finding 2026-04-18): on runs where the primary model
    is healthy, the LLM sometimes returns only ``{iso, confidence, resolved_from,
    source, is_ambiguous}`` and omits ``type``/``text``/``start``/``end``. The
    previous guardrail treated any missing canonical key as fatal, so
    ``normalize_tasks`` silently dropped otherwise valid tasks. Extracted data
    loss was invisible in the report (only ``missed_task`` surfaced). This
    coercion layer applies Postel's principle — be liberal in what you accept,
    strict in what you emit — while still returning ``None`` for inputs that
    are structurally unsalvageable (bad ``type``, out-of-range ``confidence``,
    unparseable ``iso``).

    Inference rules (no phrase enumeration, only schema shape):

    - ``text`` falls back to ``resolved_from`` when missing.
    - ``type`` is inferred from the available fields when missing or ``None``:
      a valid ``iso`` → ``exact``; non-empty ``start``/``end`` → ``range``;
      a non-empty ``text``/``resolved_from`` → ``relative``; otherwise
      ``none``.
    - ``source`` defaults to ``"llm"`` (nothing else emits ``deadline_v2``).
    - ``is_ambiguous`` defaults to ``False``.
    - ``start``/``end`` default to ``None`` when missing.
    """
    if not isinstance(d, dict):
        return None
    out: dict = {}

    iso_raw = d.get("iso")
    iso = iso_raw if isinstance(iso_raw, str) and iso_raw else None
    if iso is not None and not _is_iso_date(iso):
        return None
    out["iso"] = iso

    for key in ("start", "end"):
        v = d.get(key)
        if v is not None and (not isinstance(v, str) or (v and not _is_iso_date(v))):
            return None
        out[key] = v if isinstance(v, str) and v else None

    text = d.get("text")
    if text is None or not isinstance(text, str):
        text = d.get("resolved_from") if isinstance(d.get("resolved_from"), str) else None
    out["text"] = text
    out["resolved_from"] = d.get("resolved_from") if isinstance(d.get("resolved_from"), str) else text

    conf = d.get("confidence")
    if conf is None:
        return None
    if not isinstance(conf, (int, float)):
        return None
    if conf < 0 or conf > 1:
        return None
    out["confidence"] = float(conf)

    src = d.get("source")
    out["source"] = src if src == "llm" else "llm"

    amb = d.get("is_ambiguous")
    out["is_ambiguous"] = amb if isinstance(amb, bool) else False

    d_type = d.get("type")
    if d_type in _VALID_DEADLINE_TYPES:
        out["type"] = d_type
    elif d_type is None:
        if out["iso"]:
            out["type"] = "exact"
        elif out["start"] or out["end"]:
            out["type"] = "range"
        elif isinstance(out["text"], str) and out["text"].strip():
            out["type"] = "relative"
        else:
            out["type"] = "none"
    else:
        return None

    wo = d.get("week_offset")
    if wo in _VALID_WEEK_OFFSETS:
        out["week_offset"] = wo
    elif wo is None:
        out["week_offset"] = None
    else:
        # Unknown string from LLM — treat as ambiguous rather than rejecting
        out["week_offset"] = "unknown"

    # V2 neuro-symbolic metadata — pass through verbatim so temporal_resolve
    # can run the phrase-class handlers.  These keys did not exist when this
    # function was first written; previously they were silently dropped, which
    # caused the V2 resolver path to never execute even when the LLM output
    # them correctly.
    phrase_class = d.get("phrase_class")
    out["phrase_class"] = phrase_class if isinstance(phrase_class, str) else None

    phrase_params = d.get("phrase_params")
    out["phrase_params"] = phrase_params if isinstance(phrase_params, dict) else None

    return out


def _empty_deadline_v2() -> dict:
    """Canonical ``type="none"`` deadline_v2 — identical in shape to what the LLM
    emits for a genuinely date-less task (e.g. "finalize whenever").

    Used for graceful degradation in ``_normalize_task``: when the LLM omits the
    ``deadline_v2`` object entirely, or emits one that is unsalvageable (missing
    ``confidence``, bad ``type``/``iso``), a *valid-title* task must not be
    discarded over a single optional field. Substituting this shape keeps the
    task as a visible pending item flagged "Missing: deadline" instead of
    silently dropping it. Confidence is 0.0 because we have no deadline signal.
    """
    return {
        "iso": None,
        "start": None,
        "end": None,
        "text": None,
        "resolved_from": None,
        "confidence": 0.0,
        "source": "llm",
        "is_ambiguous": False,
        "type": "none",
        "week_offset": None,
        "phrase_class": None,
        "phrase_params": None,
    }


def _normalize_priority(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if value in {"high", "medium", "low"}:
        return value
    return None


def _normalize_uncertainty(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    u_type = value.get("type")
    reason = value.get("reason")
    if u_type not in {"ambiguous", "missing", "conflict"}:
        return None
    if reason is not None and not isinstance(reason, str):
        return None
    return {"type": u_type, "reason": reason}


def _flat_deadline_from_v2(deadline_v2: dict) -> str | None:
    """Map deadline_v2 to a single YYYY-MM-DD for API/eval when the model resolved a concrete day."""
    d_type = deadline_v2.get("type")
    if d_type == "exact":
        iso = deadline_v2.get("iso")
        return iso if isinstance(iso, str) and _is_iso_date(iso) else None
    if d_type == "relative":
        iso = deadline_v2.get("iso")
        if isinstance(iso, str) and _is_iso_date(iso):
            return iso
        return None
    if d_type == "range":
        for key in ("end", "iso", "start"):
            v = deadline_v2.get(key)
            if isinstance(v, str) and _is_iso_date(v):
                return v
        return None
    return None


def _sanitize_title(title: str, deadline_v2: dict) -> str:
    """If the title ends with the same phrase as deadline_v2.text, strip that suffix.

    Thin format guardrail only — uses the model-provided deadline phrase, not
    a hardcoded keyword list.
    """
    dl_text = (deadline_v2.get("text") or "").strip()
    if not dl_text or len(dl_text) < 3:
        return title
    t = title.rstrip()
    if t.lower().endswith(dl_text.lower()):
        trimmed = t[: len(t) - len(dl_text)].rstrip(" ,;-–—")
        return trimmed if trimmed else title
    return title


def _normalize_task(item: dict, anchor: date | None, source_text: str | None = None) -> dict | None:
    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    deadline_v2 = _coerce_deadline_v2(item.get("deadline_v2"))
    if deadline_v2 is None:
        # Graceful degradation: a task with a valid title must not be discarded
        # just because its deadline is missing or unsalvageable (LLM omitted the
        # deadline_v2 wrapper, or emitted one without `confidence` / with a bad
        # type). Keep it with an explicit no-deadline so it surfaces as a pending
        # item flagged "Missing: deadline" — not vanished silently. The drop on a
        # single field-level omission was amplifying LLM non-determinism into
        # total task loss (real-world dogfooding finding, 2026-05-26).
        deadline_v2 = _empty_deadline_v2()
    if anchor:
        deadline_v2 = enrich_deadline_v2_with_symbolic_iso(deadline_v2, anchor, source_text)
    confidence = item.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)):
            return None
        confidence = max(0.0, min(1.0, float(confidence)))

    deadline = _flat_deadline_from_v2(deadline_v2)
    sanitized_title = _sanitize_title(title.strip(), deadline_v2)
    # Round 13: pull time-of-day from the LLM's verbatim deadline phrase
    # (deadline_v2.text). Resolved_from is the fallback when text is empty —
    # both carry the original "3:00 PM ICT" / "trước 17:00 ngày 12/06/2026"
    # style string. Result is a ``datetime.time`` or None.
    dl_phrase = (deadline_v2.get("text") or deadline_v2.get("resolved_from") or "")
    deadline_time = _extract_time_of_day(dl_phrase) if isinstance(dl_phrase, str) else None
    eq = item.get("evidence_quote")
    evidence_quote = eq.strip() if isinstance(eq, str) and eq.strip() else None
    # Phase 6.6 (2026-06-03): the LLM emits ``recurrence_rule`` when it
    # detects a recurring pattern in the text. Pipeline policy is suggest
    # (not auto-apply) — we vet it through the whitelist and surface it as
    # ``recurrence_suggested`` so the UI can show an "Apply" button. A
    # malformed RRULE drops the field (graceful degradation) rather than
    # rejecting the whole task — we still extracted a valid title.
    recurrence_suggested: str | None = None
    raw_recurrence = item.get("recurrence_rule")
    if isinstance(raw_recurrence, str) and raw_recurrence.strip():
        try:
            recurrence_suggested = validate_rrule(raw_recurrence)
        except RecurrenceError:
            recurrence_suggested = None
    return {
        "title": sanitized_title,
        "description": item.get("description") if isinstance(item.get("description"), str) else None,
        "assignee": item.get("assignee") if isinstance(item.get("assignee"), str) else None,
        "source_ref": item.get("source_ref") if isinstance(item.get("source_ref"), str) else None,
        "deadline": deadline if isinstance(deadline, str) and _is_iso_date(deadline) else None,
        "deadline_time": deadline_time,
        "deadline_v2": deadline_v2,
        "priority": _normalize_priority(item.get("priority")),
        "confidence": confidence,
        "uncertainty": _normalize_uncertainty(item.get("uncertainty")),
        "evidence_quote": evidence_quote,
        "recurrence_suggested": recurrence_suggested,
    }


def _stamp_assignee_canonical(
    task: dict,
    *,
    resolver: AssigneeResolver,
    user_id: str | None,
) -> None:
    """Resolve ``task['assignee']`` via the canonical-by-data pool and stamp
    ``assignee_canonical`` + provenance fields in place.

    Q-05: we deliberately keep the raw ``assignee`` field untouched so the UI
    can still display the user's exact phrasing (e.g. "Bạn Hương"). The
    ``assignee_canonical`` field is what downstream matching, dedupe and eval
    should use. When no pool match is found, canonical equals raw with
    ``source="passthrough"`` so consumers can distinguish a pool-grounded
    decision from a first-time-seen name.
    """
    raw = task.get("assignee") if isinstance(task.get("assignee"), str) else None
    result = resolver.resolve(raw, user_id=user_id)
    if result is None:
        task["assignee_canonical"] = None
        task["assignee_canonical_source"] = None
        task["assignee_canonical_similarity"] = None
        return
    task["assignee_canonical"] = result.canonical
    task["assignee_canonical_source"] = result.source
    task["assignee_canonical_similarity"] = round(result.similarity, 4)


def normalize_tasks(state: PipelineState) -> dict:
    extracted = state.get("extracted_tasks", [])
    errors = list(state.get("errors", []))
    if not extracted:
        return {"normalized_tasks": [], "errors": errors}

    meta = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    sent_at = meta.get("sent_at")
    anchor = parse_anchor_date(str(sent_at)) if sent_at else None
    cleaned_text = state.get("cleaned_text") if isinstance(state.get("cleaned_text"), str) else None

    resolver = get_default_resolver()
    user_id_raw = state.get("user_id")
    user_id = user_id_raw if isinstance(user_id_raw, str) and user_id_raw.strip() else None

    normalized: list[dict] = []
    for idx, item in enumerate(extracted):
        if not isinstance(item, dict):
            errors.append(f"normalize_tasks: task[{idx}] is not an object")
            continue
        task = _normalize_task(item, anchor, source_text=cleaned_text)
        if task is None:
            errors.append(f"normalize_tasks: task[{idx}] rejected by schema guardrail")
            continue
        _stamp_assignee_canonical(task, resolver=resolver, user_id=user_id)
        normalized.append(task)

    return {"normalized_tasks": normalized, "errors": errors}
