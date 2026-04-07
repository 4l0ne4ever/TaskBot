#!/usr/bin/env python3
"""
Compare evaluation results from multiple methods side-by-side.
Generates both terminal output and a markdown comparison report.

Usage:
  python tests/eval/compare_results.py tests/eval/results/rule.json tests/eval/results/single_llm.json tests/eval/results/pipeline.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text("utf-8"))


def _print_table(header: str, sep: str, rows: list[str]):
    print(header)
    print(sep)
    for r in rows:
        print(r)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: compare_results.py result1.json [result2.json ...]", file=sys.stderr)
        return 1

    results = [(Path(p).stem, _load(p)) for p in sys.argv[1:]]

    header = f"{'Metric':<24}" + "".join(f"{name:>16}" for name, _ in results)
    sep = "-" * len(header)

    overall_rows = [
        ("Title F1", lambda r: r["overall"]["title_f1"]["f1"]),
        ("Title Precision", lambda r: r["overall"]["title_f1"]["precision"]),
        ("Title Recall", lambda r: r["overall"]["title_f1"]["recall"]),
        ("Assignee F1", lambda r: r["overall"]["assignee_f1"]["f1"]),
        ("Deadline Exact", lambda r: r["overall"]["deadline_exact"]),
        ("Deadline Near (+-1d)", lambda r: r["overall"]["deadline_near"]),
        ("Conflict F1", lambda r: r["overall"]["conflict_f1"]["f1"]),
        ("Conflict Precision", lambda r: r["overall"]["conflict_f1"]["precision"]),
        ("Conflict Recall", lambda r: r["overall"]["conflict_f1"]["recall"]),
        ("Samples", lambda r: r["overall"]["counts"]["samples"]),
        ("Runtime Errors", lambda r: r.get("runtime_error_count", len(r.get("errors", [])))),
        ("Fully Correct %", lambda r: sum(1 for d in r.get("sample_details", []) if d.get("is_correct")) / max(len(r.get("sample_details", [r])), 1) * 100),
    ]

    print("\n=== OVERALL COMPARISON ===\n")
    rows = []
    for label, fn in overall_rows:
        vals = []
        for _, r in results:
            try:
                v = fn(r)
            except (KeyError, TypeError):
                v = "n/a"
            if isinstance(v, float):
                vals.append(f"{v:>16.4f}")
            elif isinstance(v, int):
                vals.append(f"{v:>16}")
            else:
                vals.append(f"{str(v):>16}")
        rows.append(f"{label:<24}" + "".join(vals))
    _print_table(header, sep, rows)

    cats = set()
    for _, r in results:
        cats.update(r.get("per_category", {}).keys())

    if cats:
        core_cats = sorted(c for c in cats if not c.startswith("edge_"))
        edge_cats = sorted(c for c in cats if c.startswith("edge_"))

        print(f"\n=== PER-CATEGORY TITLE F1 ===\n")
        cat_header = f"{'Category':<24}" + "".join(f"{n:>16}" for n, _ in results)
        print(cat_header)
        print("-" * len(cat_header))
        for cat in core_cats + edge_cats:
            if cat == core_cats[0] if core_cats else "":
                pass
            if edge_cats and cat == edge_cats[0]:
                print(f"{'--- Edge Cases ---':<24}" + "".join(f"{'':>16}" for _ in results))
            vals = []
            for _, r in results:
                d = r.get("per_category", {}).get(cat)
                if d:
                    vals.append(f"{d['title_f1']['f1']:>16.4f}")
                else:
                    vals.append(f"{'n/a':>16}")
            print(f"{cat:<24}" + "".join(vals))

    err_types = set()
    for _, r in results:
        err_types.update(r.get("error_type_distribution", {}).keys())
    if err_types:
        print(f"\n=== ERROR TYPE DISTRIBUTION ===\n")
        eh = f"{'Error Type':<28}" + "".join(f"{n:>16}" for n, _ in results)
        print(eh)
        print("-" * len(eh))
        for et in sorted(err_types):
            vals = []
            for _, r in results:
                cnt = r.get("error_type_distribution", {}).get(et, 0)
                vals.append(f"{cnt:>16}")
            print(f"{et:<28}" + "".join(vals))

    md_path = Path(sys.argv[1]).parent / "comparison_report.md"
    _write_md_report(results, cats, err_types, md_path)
    print(f"\nMarkdown report: {md_path}")

    return 0


def _write_md_report(results, cats, err_types, out_path: Path):
    lines = []
    lines.append("# Evaluation Comparison Report")
    lines.append(f"\nGenerated: {datetime.now().isoformat()[:19]}")
    lines.append(f"Methods: {', '.join(n for n, _ in results)}\n")

    lines.append("## Overall Metrics\n")
    header = "| Metric | " + " | ".join(n for n, _ in results) + " |"
    sep = "|--------|" + "|".join(["-------"] * len(results)) + "|"
    lines.append(header)
    lines.append(sep)

    metric_rows = [
        ("Title F1", lambda r: f"{r['overall']['title_f1']['f1']:.4f}"),
        ("Title Precision", lambda r: f"{r['overall']['title_f1']['precision']:.4f}"),
        ("Title Recall", lambda r: f"{r['overall']['title_f1']['recall']:.4f}"),
        ("Assignee F1", lambda r: f"{r['overall']['assignee_f1']['f1']:.4f}"),
        ("Deadline Exact", lambda r: f"{r['overall']['deadline_exact']:.4f}"),
        ("Deadline Near", lambda r: f"{r['overall']['deadline_near']:.4f}"),
        ("Conflict F1", lambda r: f"{r['overall']['conflict_f1']['f1']:.4f}"),
    ]
    for label, fn in metric_rows:
        vals = []
        for _, r in results:
            try:
                vals.append(fn(r))
            except (KeyError, TypeError):
                vals.append("n/a")
        lines.append(f"| {label} | " + " | ".join(vals) + " |")

    lines.append("\n## Per-Category Title F1\n")
    header = "| Category | " + " | ".join(n for n, _ in results) + " |"
    sep = "|----------|" + "|".join(["-------"] * len(results)) + "|"
    lines.append(header)
    lines.append(sep)
    for cat in sorted(cats):
        vals = []
        for _, r in results:
            d = r.get("per_category", {}).get(cat)
            vals.append(f"{d['title_f1']['f1']:.4f}" if d else "n/a")
        lines.append(f"| {cat} | " + " | ".join(vals) + " |")

    lines.append("\n## Error Type Comparison\n")
    if err_types:
        header = "| Error Type | " + " | ".join(n for n, _ in results) + " |"
        sep = "|------------|" + "|".join(["-------"] * len(results)) + "|"
        lines.append(header)
        lines.append(sep)
        for et in sorted(err_types):
            vals = [str(r.get("error_type_distribution", {}).get(et, 0)) for _, r in results]
            lines.append(f"| {et} | " + " | ".join(vals) + " |")

    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
