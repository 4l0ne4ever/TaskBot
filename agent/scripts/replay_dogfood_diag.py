"""DIAGNOSTIC replay — runs the real pipeline nodes (parse->extract->normalize->
validate) on the exact synced raw_text of the 9 dogfood docs of interest, and
STOPS before save_tasks. No DB writes. Prints, per doc:

  - extracted task titles (extract node output)
  - per task: normalized deadline (flat), phrase_class, deadline_v2.iso
  - per task: validate confidence, decision band, missing fields, uncertainty

Purpose: separate extract-miss vs validate-abstain for the 4 missed docs, and
classification-vs-resolver for the 5 wrong-deadline docs.
"""
from __future__ import annotations

import asyncio
import os

import psycopg2

# 9 docs of interest, keyed by a unique substring present in raw_text.
MARKERS = {
    # --- 4 missed (tasks_extracted = 0) ---
    "hc01_henderson_draft": "handle the following",
    "hc07_faq_update": "onboarding FAQ",
    "hc09_expense_recon": "expense reconciliation",
    "hc10_hotfix_deploy": "hotfix v2.4.1",
    # --- 5 wrong-deadline ---
    "hc02_market_research": "nghiên cứu thị trường",
    "hc04_launch_slides": "Beta launch readout",
    "hc06_vendor_contract": "Acme Corp",
    "hc08_interview_synthesis": "interview synthesis",
    "nm05_thread_reassign": "Q2 compliance report",
}

EXPECTED = {
    "hc01_henderson_draft": "Draft Henderson proposal, deadline 2026-06-10",
    "hc07_faq_update": "Update onboarding FAQ, deadline 2026-06-11",
    "hc09_expense_recon": "Expense reconciliation, deadline 2026-06-09",
    "hc10_hotfix_deploy": "Deploy hotfix v2.4.1, deadline 2026-06-22",
    "hc02_market_research": "deadline 2026-06-12 (got 2026-05-26)",
    "hc04_launch_slides": "deadline 2026-06-20 (got 2026-05-29)",
    "hc06_vendor_contract": "deadline 2026-06-16 (got 2026-05-26)",
    "hc08_interview_synthesis": "deadline 2026-06-25 (got 2026-05-27)",
    "nm05_thread_reassign": "assignee Lan, new deadline 2026-06-16 (got 2026-06-01)",
}


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL") or ""
    # psycopg2 wants plain postgresql:// (strip +asyncpg)
    return url.replace("+asyncpg", "")


def fetch_raw_texts() -> dict[str, dict]:
    conn = psycopg2.connect(_db_url())
    out: dict[str, dict] = {}
    try:
        with conn.cursor() as cur:
            for key, marker in MARKERS.items():
                cur.execute(
                    """
                    select d.id, d.raw_text, d.source_type, d.created_at
                    from source_documents d
                    join users u on u.id = d.user_id
                    where u.email = %s and d.raw_text ilike %s
                    order by d.created_at limit 1
                    """,
                    ("emilywithherpet@gmail.com", f"%{marker}%"),
                )
                row = cur.fetchone()
                if row:
                    out[key] = {
                        "doc_id": str(row[0]),
                        "raw_text": row[1],
                        "source_type": row[2] or "gmail",
                        "created_at": row[3],
                    }
    finally:
        conn.close()
    return out


def run_one(key: str, doc: dict) -> None:
    import importlib

    validate_mod = importlib.import_module("app.pipeline.nodes.validate_tasks")
    from app.pipeline.nodes.extract_tasks import extract_tasks
    from app.pipeline.nodes.normalize_tasks import normalize_tasks
    from app.pipeline.nodes.parse_input import parse_input

    # Neutralize the cross-source DB loader so validate runs offline.
    validate_mod.load_cross_source_candidates_sync = lambda *a, **k: []  # type: ignore

    state: dict = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "source_doc_id": doc["doc_id"],
        "source_type": doc["source_type"],
        "raw_content": doc["raw_text"],
        "existing_tasks": [],  # short-circuits DB lookup in validate
        "metadata": {},
    }

    for node in (parse_input, extract_tasks, normalize_tasks, validate_mod.validate_tasks):
        try:
            delta = node(state)
            if isinstance(delta, dict):
                state.update(delta)
        except Exception as exc:  # noqa: BLE001
            print(f"    !! {node.__name__} raised: {type(exc).__name__}: {exc}")
            return

    extracted = state.get("extracted_tasks") or []
    normalized = state.get("normalized_tasks") or []
    validated = state.get("validated_tasks") or []

    print(f"\n### {key}")
    print(f"    expected : {EXPECTED.get(key, '?')}")
    print(f"    extract  : {len(extracted)} task(s)")
    for t in extracted:
        has_dv2 = "deadline_v2" in t
        dv2 = t.get("deadline_v2")
        print(
            f"      - title={t.get('title')!r}\n"
            f"        deadline_v2 present={has_dv2} value={dv2!r}"
        )
    if not extracted:
        print("    >>> EXTRACT-MISS: LLM returned zero tasks from this email.")
        return
    print(f"    normalize kept {len(normalized)}/{len(extracted)}")
    for t in normalized:
        dv2 = t.get("deadline_v2") or {}
        print(
            f"    norm task: title={t.get('title')!r}\n"
            f"               assignee={t.get('assignee')!r} deadline(flat)={t.get('deadline')!r}\n"
            f"               phrase_class={t.get('phrase_class')!r} "
            f"deadline_v2.type={dv2.get('type')!r} deadline_v2.iso={dv2.get('iso')!r} "
            f"resolved_from={dv2.get('resolved_from') or dv2.get('text')!r}"
        )
    for t in validated:
        print(
            f"    valid task: title={t.get('title')!r} confidence={t.get('confidence')!r} "
            f"band={t.get('decision_band') or t.get('band')!r} "
            f"missing={t.get('missing')!r} uncertainty={'set' if t.get('uncertainty') else None}"
        )
    errs = [e for e in (state.get("errors") or []) if "normalize" in e or "extract" in e]
    if errs:
        print(f"    errors   : {errs}")


def main() -> None:
    docs = fetch_raw_texts()
    print(f"Fetched {len(docs)}/{len(MARKERS)} docs from DB.")
    missing = set(MARKERS) - set(docs)
    if missing:
        print(f"!! could not locate: {sorted(missing)}")
    for key in MARKERS:
        if key in docs:
            run_one(key, docs[key])


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
