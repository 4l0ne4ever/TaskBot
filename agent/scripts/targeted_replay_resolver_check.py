"""Targeted replay to distinguish two hypotheses for the wrong-deadline bug
that persists in pinned Cerebras production sync:

  (A) LLM emits phrase_class='named_weekday' alongside the correct ISO, and
      the resolver in normalize_tasks OVERRIDES the ISO with a next-weekday
      computation (wrong direction).

  (B) The LLM emits a wrong ISO directly — pure single-pass non-determinism
      that the prior pinned measurement (N=5) averaged away.

The prior measurement script set metadata={} → sent_at=None → anchor=None →
resolver skipped entirely → would have masked hypothesis (A). This script sets
anchor explicitly to 2026-05-23 (when gmail-test-sender originally sent the
test emails), which is the same anchor production sees.

For each of 3 emails that produced wrong deadlines in today's sync, run
parse_input → extract_tasks → normalize_tasks and dump:

  - LLM-emitted deadline_v2 (extracted_tasks): phrase_class, iso, text,
    resolved_from
  - Anchor actually used by the resolver
  - Post-resolver deadline_v2 (normalized_tasks): type, iso, phrase_class
  - Final flat deadline

If LLM iso != final flat deadline AND phrase_class is named_weekday → (A).
If LLM iso is already wrong → (B).
"""
from __future__ import annotations

import json
import os
import sys

import psycopg2

# 3 emails confirmed wrong in today's sync (09:07-09:13, pinned Cerebras run).
MARKERS = {
    "hc04_beta_slides":  ("Beta launch readout",   "2026-06-20", "2026-05-29"),
    "hc01_henderson":    ("handle the following",  "2026-06-10", "2026-05-26"),
    "hc06_acme_vendor":  ("Acme Corp",             "2026-06-16", "2026-05-26"),
}


def fetch_raws() -> dict[str, tuple[str, str]]:
    url = (os.environ.get("DATABASE_URL") or "").replace("+asyncpg", "")
    conn = psycopg2.connect(url)
    out: dict[str, tuple[str, str]] = {}
    try:
        with conn.cursor() as cur:
            for key, (marker, _exp, _got) in MARKERS.items():
                cur.execute(
                    """select d.id, d.raw_text, d.source_type
                       from source_documents d join users u on u.id=d.user_id
                       where u.email=%s and d.raw_text ilike %s
                       order by d.created_at desc limit 1""",
                    ("emilywithherpet@gmail.com", f"%{marker}%"),
                )
                row = cur.fetchone()
                if row:
                    out[key] = (row[1], row[2] or "gmail")
    finally:
        conn.close()
    return out


def run_one(key: str, raw: str, stype: str, expected: str, got_in_prod: str) -> None:
    import importlib
    from app.pipeline.nodes.extract_tasks import extract_tasks
    from app.pipeline.nodes.parse_input import parse_input

    # Use importlib to get the real module (nodes/__init__ shadows submodules).
    norm_mod = importlib.import_module("app.pipeline.nodes.normalize_tasks")

    # Production-realistic state: sent_at = 2026-05-23 (when the test emails
    # were sent). This is the anchor the resolver will see in production.
    state: dict = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "source_doc_id": "00000000-0000-0000-0000-000000000000",
        "source_type": stype,
        "raw_content": raw,
        "metadata": {"sent_at": "2026-05-23T08:00:00+00:00"},
    }

    for node in (parse_input, extract_tasks):
        delta = node(state)
        if isinstance(delta, dict):
            state.update(delta)

    extracted_pre = [dict(t) for t in (state.get("extracted_tasks") or [])]
    # Save a deep copy of deadline_v2 before normalize_tasks mutates it.
    pre_dl_v2 = [dict(t.get("deadline_v2") or {}) for t in extracted_pre]

    delta = norm_mod.normalize_tasks(state)
    if isinstance(delta, dict):
        state.update(delta)
    normalized = state.get("normalized_tasks") or []

    print(f"\n{'=' * 80}\n### {key}")
    print(f"    expected deadline: {expected}")
    print(f"    got in production: {got_in_prod}")
    print(f"    anchor passed to resolver: 2026-05-23 (from metadata.sent_at)")
    print(f"    extract → {len(extracted_pre)} task(s); normalize kept {len(normalized)}")

    for i, (raw_t, pre_dl, norm_t) in enumerate(zip(extracted_pre, pre_dl_v2, normalized)):
        print(f"\n    --- task[{i}] ---")
        print(f"    title          : {norm_t.get('title')!r}")

        # LLM-emitted (before resolver runs)
        print(f"    LLM-emitted deadline_v2:")
        print(f"        phrase_class : {pre_dl.get('phrase_class')!r}")
        print(f"        iso          : {pre_dl.get('iso')!r}")
        print(f"        type         : {pre_dl.get('type')!r}")
        print(f"        text         : {pre_dl.get('text')!r}")
        print(f"        resolved_from: {pre_dl.get('resolved_from')!r}")

        # Post-resolver (what normalize_tasks produced)
        post_dl = norm_t.get("deadline_v2") or {}
        print(f"    post-resolver deadline_v2:")
        print(f"        phrase_class : {post_dl.get('phrase_class')!r}")
        print(f"        iso          : {post_dl.get('iso')!r}")
        print(f"        type         : {post_dl.get('type')!r}")
        print(f"    FLAT DEADLINE  : {norm_t.get('deadline')!r}")

        # Verdict per task
        llm_iso = pre_dl.get("iso")
        final = norm_t.get("deadline")
        if llm_iso and final and llm_iso != final:
            print(f"    >>> RESOLVER OVERRODE: LLM said {llm_iso}, resolver returned {final}  (Hypothesis A signal)")
        elif llm_iso and final and llm_iso == final and final != expected:
            print(f"    >>> LLM emitted wrong ISO directly: {llm_iso}  (Hypothesis B signal)")
        elif llm_iso and final and llm_iso == final == expected:
            print(f"    >>> Correct on this attempt — variance window")
        else:
            print(f"    >>> Other path (no ISO emitted, or none → none)")


def main() -> None:
    raws = fetch_raws()
    print(f"Fetched {len(raws)}/{len(MARKERS)} target docs.")
    for key, (_marker, expected, got_in_prod) in MARKERS.items():
        if key in raws:
            raw, stype = raws[key]
            run_one(key, raw, stype, expected, got_in_prod)
        else:
            print(f"  !! missing: {key}")


if __name__ == "__main__":
    main()
