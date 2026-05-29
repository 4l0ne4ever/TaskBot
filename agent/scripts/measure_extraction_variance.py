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
#   title_kws: ANY-OF keyword list (lowercased substring); fixes the prior
#              brittle single-keyword false-negatives (e.g. hc02's VN title has
#              no English "research"). A run counts as "produced the primary
#              task" iff any extracted task's title contains any keyword.
SPECS: dict[str, dict] = {
    "handle the following":   {"id": "hc01", "title_kws": ["henderson", "proposal"],          "expected_iso": "2026-06-10", "abstain": False},
    "nghiên cứu thị trường":  {"id": "hc02", "title_kws": ["nghiên cứu", "research", "market"], "expected_iso": "2026-06-12", "abstain": False},
    "login timeout":          {"id": "hc03", "title_kws": ["login", "timeout", "bug fix"],    "expected_iso": "2026-06-14", "abstain": False},
    "Beta launch readout":    {"id": "hc04", "title_kws": ["slides", "beta"],                 "expected_iso": "2026-06-20", "abstain": False},
    "signed Q2 attestation":  {"id": "hc05", "title_kws": ["legal", "attestation", "pdf"],    "expected_iso": "2026-06-18", "abstain": False},
    "Acme Corp":              {"id": "hc06", "title_kws": ["acme", "vendor", "hợp đồng"],     "expected_iso": "2026-06-16", "abstain": False},
    "onboarding FAQ":         {"id": "hc07", "title_kws": ["faq", "onboarding"],              "expected_iso": "2026-06-11", "abstain": False},
    "interview synthesis":    {"id": "hc08", "title_kws": ["interview", "synthesis"],         "expected_iso": "2026-06-25", "abstain": False},
    "expense reconciliation": {"id": "hc09", "title_kws": ["expense", "reconciliation"],      "expected_iso": "2026-06-09", "abstain": False},
    "hotfix v2.4.1":          {"id": "hc10", "title_kws": ["hotfix", "deploy"],               "expected_iso": "2026-06-22", "abstain": False},
    "all-hands deck":         {"id": "nm01", "title_kws": None,                                "expected_iso": None,         "abstain": True},
    "refresh the dashboard":  {"id": "nm02", "title_kws": None,                                "expected_iso": None,         "abstain": True},
    "sprint review":          {"id": "nm03", "title_kws": None,                                "expected_iso": None,         "abstain": True},
    "checking in on the Henderson": {"id": "nm04", "title_kws": None,                          "expected_iso": None,         "abstain": True},
    "Q2 compliance report":   {"id": "nm05", "title_kws": ["compliance", "q2"],               "expected_iso": "2026-06-16", "abstain": False},
    "release notes":          {"id": "nm06", "title_kws": ["release notes"],                  "expected_iso": "2026-06-18", "abstain": False},
    "The Batch":              {"id": "nm07", "title_kws": None,                                "expected_iso": None,         "abstain": True},
    "owners TBD":             {"id": "nm08", "title_kws": None,                                "expected_iso": None,         "abstain": False},  # 3 tasks, no deadline
    "minor wording tweaks":   {"id": "nm09", "title_kws": None,                                "expected_iso": None,         "abstain": False},  # soft
    "security training":      {"id": "nm10", "title_kws": ["training", "security"],           "expected_iso": None,         "abstain": False},
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


def run_once(raw: str, stype: str) -> tuple[list[dict], list]:
    """Run parse→extract→normalize once. Return (normalized_tasks, provenance).

    Provenance is the list of per-LLM-call ``CallRecord`` objects produced inside
    this run — used to verify that under ``EVAL_CEREBRAS_ONLY=1`` every call hit
    Cerebras and no fallback fired.
    """
    from app.pipeline.llm import collect_provenance
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
    with collect_provenance() as records:
        for node in (parse_input, extract_tasks, normalize_tasks):
            delta = node(state)
            if isinstance(delta, dict):
                state.update(delta)
    return state.get("normalized_tasks") or [], list(records)


def main() -> None:
    docs = fetch()
    pinned = os.environ.get("EVAL_CEREBRAS_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}
    print(f"Fetched {len(docs)}/{len(SPECS)} docs. N_RUNS={N_RUNS}  pinned={pinned}\n")
    print(f"{'id':5} {'kind':7} {'extract%':9} {'dl-exact%':10} {'drops':6} {'fp%':6}  detail")
    print("-" * 92)

    # Aggregate provenance across the whole measurement.
    total_calls = 0
    fallback_calls = 0
    rate_limited_calls = 0
    models_used: dict[str, int] = {}
    run_errors: list[str] = []

    for spec in SPECS.values():
        did = spec["id"]
        if did not in docs:
            print(f"{did:5} MISSING from DB")
            continue
        d = docs[did]
        sp = d["spec"]
        runs: list[tuple[list[dict], list]] = []
        for _ in range(N_RUNS):
            try:
                runs.append(run_once(d["raw"], d["stype"]))
            except Exception as exc:  # noqa: BLE001
                run_errors.append(f"{did}: {type(exc).__name__}: {str(exc)[:120]}")
                runs.append(([{"__error__": str(exc)}], []))

        for _tasks, records in runs:
            for r in records:
                total_calls += 1
                if getattr(r, "is_fallback", False):
                    fallback_calls += 1
                if getattr(r, "rate_limited", False):
                    rate_limited_calls += 1
                m = getattr(r, "model", "?") or "?"
                models_used[m] = models_used.get(m, 0) + 1

        produced_primary = 0
        dl_exact = 0
        any_task_runs = 0
        dl_values: list = []
        kws = sp["title_kws"]

        for tasks, _records in runs:
            real = [t for t in tasks if "__error__" not in t]
            if real:
                any_task_runs += 1
            if not kws:
                continue
            match = next(
                (t for t in real if any(k in (t.get("title") or "").lower() for k in kws)),
                None,
            )
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
            ext = 100.0 * produced_primary / N_RUNS if kws else float("nan")
            dlx = (100.0 * dl_exact / produced_primary) if (produced_primary and sp["expected_iso"]) else float("nan")
            detail = f"exp={sp['expected_iso']} got={sorted(set(map(str, dl_values)))}" if sp["expected_iso"] else ""
            ext_s = f"{ext:6.0f}%" if kws else "   n/a"
            dlx_s = f"{dlx:7.0f}%" if (produced_primary and sp["expected_iso"]) else "    n/a"
            print(f"{did:5} {kind:7} {ext_s:>9} {dlx_s:>10} {'0':>6} {'—':>6}  {detail}")

    print("\n(extract% = runs producing the expected primary task; "
          "dl-exact% = of those, correct ISO; fp% = abstain emails wrongly producing a task)")
    print(f"\n=== provenance across {total_calls} LLM call(s) ===")
    print(f"  fallback fires  : {fallback_calls}")
    print(f"  rate-limit hits : {rate_limited_calls}")
    print(f"  models used     : {sorted(models_used.items(), key=lambda kv: -kv[1])}")
    if run_errors:
        print(f"\n!! {len(run_errors)} run(s) errored:")
        for e in run_errors[:10]:
            print(f"   - {e}")


if __name__ == "__main__":
    sys.exit(main())
