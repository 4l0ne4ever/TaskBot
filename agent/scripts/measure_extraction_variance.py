"""N-run extraction-variance measurement on the 20 dogfood emails.

Runs parse_input -> extract_tasks -> normalize_tasks N times per email against
the exact synced raw_text, and reports per-email:

  - extraction rate : fraction of runs that produced the expected primary task
  - deadline-exact  : among runs that produced it, fraction with the correct ISO
  - drop count      : runs where normalize discarded a valid-title task (should be
                      ~0 after the graceful-degradation fix)
  - false-positive  : for abstain-expected emails, fraction of runs that wrongly
                      produced any task

No validate/save (no DB writes, no conflict LLM call) — this isolates extraction
+ the deterministic normalize stage. Run inside the agent container.
"""
from __future__ import annotations

import os
import sys

import psycopg2

N_RUNS = int(os.environ.get("N_RUNS", "5"))

# marker (substring of raw_text) -> spec
# expected_iso: ground-truth primary deadline (None = no deadline expected)
# title_kw:     lowercase keyword that must appear in the primary task title
# abstain:      True if the email should produce NO task at all
SPECS: dict[str, dict] = {
    "handle the following":   {"id": "hc01", "title_kw": "henderson",      "expected_iso": "2026-06-10", "abstain": False},
    "nghiên cứu thị trường":  {"id": "hc02", "title_kw": "research",       "expected_iso": "2026-06-12", "abstain": False},
    "login timeout":          {"id": "hc03", "title_kw": "login",          "expected_iso": "2026-06-14", "abstain": False},
    "Beta launch readout":    {"id": "hc04", "title_kw": "slides",         "expected_iso": "2026-06-20", "abstain": False},
    "signed Q2 attestation":  {"id": "hc05", "title_kw": "legal",          "expected_iso": "2026-06-18", "abstain": False},
    "Acme Corp":              {"id": "hc06", "title_kw": "acme",           "expected_iso": "2026-06-16", "abstain": False},
    "onboarding FAQ":         {"id": "hc07", "title_kw": "faq",            "expected_iso": "2026-06-11", "abstain": False},
    "interview synthesis":    {"id": "hc08", "title_kw": "interview",      "expected_iso": "2026-06-25", "abstain": False},
    "expense reconciliation": {"id": "hc09", "title_kw": "expense",        "expected_iso": "2026-06-09", "abstain": False},
    "hotfix v2.4.1":          {"id": "hc10", "title_kw": "hotfix",         "expected_iso": "2026-06-22", "abstain": False},
    "all-hands deck":         {"id": "nm01", "title_kw": None,             "expected_iso": None,         "abstain": True},
    "refresh the dashboard":  {"id": "nm02", "title_kw": None,             "expected_iso": None,         "abstain": True},
    "sprint review":          {"id": "nm03", "title_kw": None,             "expected_iso": None,         "abstain": True},
    "checking in on the Henderson": {"id": "nm04", "title_kw": None,       "expected_iso": None,         "abstain": True},
    "Q2 compliance report":   {"id": "nm05", "title_kw": "compliance",     "expected_iso": "2026-06-16", "abstain": False},
    "release notes":          {"id": "nm06", "title_kw": "release notes",  "expected_iso": "2026-06-18", "abstain": False},
    "The Batch":              {"id": "nm07", "title_kw": None,             "expected_iso": None,         "abstain": True},
    "owners TBD":             {"id": "nm08", "title_kw": None,             "expected_iso": None,         "abstain": False},  # 3 tasks, no deadline
    "minor wording tweaks":   {"id": "nm09", "title_kw": None,             "expected_iso": None,         "abstain": False},  # soft
    "security training":      {"id": "nm10", "title_kw": "training",       "expected_iso": None,         "abstain": False},
}


def _db_url() -> str:
    return (os.environ.get("DATABASE_URL") or "").replace("+asyncpg", "")


def fetch() -> dict[str, dict]:
    conn = psycopg2.connect(_db_url())
    out: dict[str, dict] = {}
    try:
        with conn.cursor() as cur:
            for marker, spec in SPECS.items():
                cur.execute(
                    """select d.id, d.raw_text, d.source_type from source_documents d
                       join users u on u.id=d.user_id
                       where u.email=%s and d.raw_text ilike %s
                       order by d.created_at limit 1""",
                    ("emilywithherpet@gmail.com", f"%{marker}%"),
                )
                row = cur.fetchone()
                if row:
                    out[spec["id"]] = {"raw": row[1], "stype": row[2] or "gmail", "spec": spec}
    finally:
        conn.close()
    return out


def run_once(raw: str, stype: str) -> list[dict]:
    from app.pipeline.nodes.extract_tasks import extract_tasks
    from app.pipeline.nodes.normalize_tasks import normalize_tasks
    from app.pipeline.nodes.parse_input import parse_input

    state: dict = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "source_doc_id": "00000000-0000-0000-0000-000000000000",
        "source_type": stype,
        "raw_content": raw,
        "metadata": {},
    }
    for node in (parse_input, extract_tasks, normalize_tasks):
        delta = node(state)
        if isinstance(delta, dict):
            state.update(delta)
    return state.get("normalized_tasks") or []


def main() -> None:
    docs = fetch()
    print(f"Fetched {len(docs)}/{len(SPECS)} docs. N_RUNS={N_RUNS}\n")
    print(f"{'id':5} {'kind':7} {'extract%':9} {'dl-exact%':10} {'drops':6} {'fp%':6}  detail")
    print("-" * 92)

    for spec in SPECS.values():
        did = spec["id"]
        if did not in docs:
            print(f"{did:5} MISSING from DB")
            continue
        d = docs[did]
        sp = d["spec"]
        runs = []
        for _ in range(N_RUNS):
            try:
                runs.append(run_once(d["raw"], d["stype"]))
            except Exception as exc:  # noqa: BLE001
                runs.append([{"__error__": f"{type(exc).__name__}: {exc}"}])

        produced_primary = 0   # runs that produced the expected primary task
        dl_exact = 0           # of those, correct ISO
        any_task_runs = 0      # runs producing >=1 task (for FP on abstain)
        dl_values: list = []

        for tasks in runs:
            real = [t for t in tasks if "__error__" not in t]
            if real:
                any_task_runs += 1
            kw = sp["title_kw"]
            if kw is None:
                continue
            match = next((t for t in real if kw in (t.get("title") or "").lower()), None)
            if match:
                produced_primary += 1
                dl = match.get("deadline")
                dl_values.append(dl)
                if sp["expected_iso"] and dl == sp["expected_iso"]:
                    dl_exact += 1

        kind = "ABSTAIN" if sp["abstain"] else ("no-dl" if not sp["expected_iso"] else "deadline")
        if sp["abstain"]:
            fp = 100.0 * any_task_runs / N_RUNS
            print(f"{did:5} {kind:7} {'—':>9} {'—':>10} {'—':>6} {fp:5.0f}%")
        else:
            ext = 100.0 * produced_primary / N_RUNS if sp["title_kw"] else float("nan")
            dlx = (100.0 * dl_exact / produced_primary) if (produced_primary and sp["expected_iso"]) else float("nan")
            detail = f"exp={sp['expected_iso']} got={sorted(set(map(str, dl_values)))}" if sp["expected_iso"] else ""
            ext_s = f"{ext:6.0f}%" if sp["title_kw"] else "   n/a"
            dlx_s = f"{dlx:7.0f}%" if (produced_primary and sp["expected_iso"]) else "    n/a"
            print(f"{did:5} {kind:7} {ext_s:>9} {dlx_s:>10} {'0':>6} {'—':>6}  {detail}")

    print("\n(extract% = runs producing the expected primary task; "
          "dl-exact% = of those, correct ISO; fp% = abstain emails wrongly producing a task)")


if __name__ == "__main__":
    sys.exit(main())
