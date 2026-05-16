from datetime import date

from app.pipeline.state import PipelineState
from app.pipeline.temporal_resolve import enrich_deadline_v2_with_symbolic_iso, parse_anchor_date
from app.services.assignee_resolver import AssigneeResolver, get_default_resolver

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


def _normalize_task(item: dict, anchor: date | None) -> dict | None:
    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    deadline_v2 = _coerce_deadline_v2(item.get("deadline_v2"))
    if deadline_v2 is None:
        return None
    if anchor:
        deadline_v2 = enrich_deadline_v2_with_symbolic_iso(deadline_v2, anchor)
    confidence = item.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)):
            return None
        confidence = max(0.0, min(1.0, float(confidence)))

    deadline = _flat_deadline_from_v2(deadline_v2)
    sanitized_title = _sanitize_title(title.strip(), deadline_v2)
    eq = item.get("evidence_quote")
    evidence_quote = eq.strip() if isinstance(eq, str) and eq.strip() else None
    return {
        "title": sanitized_title,
        "description": item.get("description") if isinstance(item.get("description"), str) else None,
        "assignee": item.get("assignee") if isinstance(item.get("assignee"), str) else None,
        "source_ref": item.get("source_ref") if isinstance(item.get("source_ref"), str) else None,
        "deadline": deadline if isinstance(deadline, str) and _is_iso_date(deadline) else None,
        "deadline_v2": deadline_v2,
        "priority": _normalize_priority(item.get("priority")),
        "confidence": confidence,
        "uncertainty": _normalize_uncertainty(item.get("uncertainty")),
        "evidence_quote": evidence_quote,
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

    resolver = get_default_resolver()
    user_id_raw = state.get("user_id")
    user_id = user_id_raw if isinstance(user_id_raw, str) and user_id_raw.strip() else None

    normalized: list[dict] = []
    for idx, item in enumerate(extracted):
        if not isinstance(item, dict):
            errors.append(f"normalize_tasks: task[{idx}] is not an object")
            continue
        task = _normalize_task(item, anchor)
        if task is None:
            errors.append(f"normalize_tasks: task[{idx}] rejected by schema guardrail")
            continue
        _stamp_assignee_canonical(task, resolver=resolver, user_id=user_id)
        normalized.append(task)

    return {"normalized_tasks": normalized, "errors": errors}
