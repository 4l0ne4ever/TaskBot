from __future__ import annotations

import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

UPDATE_TITLE_MATCH_THRESHOLD = 0.85


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def pick_task_to_reuse(
    candidates: list[Any],
    new_title: str,
    *,
    excluded_ids: set[uuid.UUID],
    threshold: float = UPDATE_TITLE_MATCH_THRESHOLD,
) -> Any | None:
    """Pick one ORM Task from candidates to update, or None to insert a new row."""
    title = new_title.strip()
    if not title:
        return None
    best = None
    best_score = -1.0
    best_ts: datetime | None = None
    for t in candidates:
        tid = getattr(t, "id", None)
        if tid is None or tid in excluded_ids:
            continue
        s = title_similarity(title, getattr(t, "title", "") or "")
        if s < threshold:
            continue
        tu = getattr(t, "updated_at", None)
        if not isinstance(tu, datetime):
            tu = None
        if s > best_score or (
            s == best_score and tu is not None and (best_ts is None or tu > best_ts)
        ):
            best_score = s
            best = t
            best_ts = tu
    return best
