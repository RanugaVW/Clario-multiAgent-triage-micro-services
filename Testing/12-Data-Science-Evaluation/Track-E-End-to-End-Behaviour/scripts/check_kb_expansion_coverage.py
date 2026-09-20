"""Track E diagnostic - local-only (no API calls) check on whether the KB
expansion (5 new documents + 1 fix to hr/course_cancellation.md) actually
retrieves for the 40 queries Track A's 99-query pilot ground truth marked as
having no correct document at all (data/retrieval_ground_truth.csv, this
project's un-modified original in Track-A-Retrieval-Quality).

This script does NOT touch anything under Track-A-Retrieval-Quality - it only
reads that CSV as reference data and calls retrieve_context() directly against
the rebuilt local Chroma index, to see what actually comes back now. It does
not update Track A's ground truth, report, or metrics.

Usage:
    python3 check_kb_expansion_coverage.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_SIDECAR_ROOT / ".env")

from app.tools.rag_tool import retrieve_context  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parent.parent / "Track-A-Retrieval-Quality" / "data" / "retrieval_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

DOMAIN_MAP = {"HR": "hr", "hr": "hr", "billing": "billing", "technical": "technical"}
RAG_SCORE_THRESHOLD = 0.70


def main() -> None:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    gap_rows = [r for r in rows if r.get("relevant_doc_ids", "").strip().lower() == "none"]

    results = []
    for r in gap_rows:
        domain = DOMAIN_MAP[r["domain"]]
        hits = retrieve_context(r["query_text"], domain, k=1)
        top = hits[0] if hits else None
        results.append({
            "query_id": r["query_id"],
            "domain": domain,
            "top_doc": top["source_file"] if top else None,
            "top_score": round(float(top["score"]), 3) if top else None,
            "above_threshold": bool(top and float(top["score"]) >= RAG_SCORE_THRESHOLD),
        })

    n_total = len(results)
    n_above = sum(1 for r in results if r["above_threshold"])
    print(f"{n_total} previously-uncovered queries checked, {n_above} now retrieve above the {RAG_SCORE_THRESHOLD} RAG threshold\n")
    for r in results:
        flag = "OK " if r["above_threshold"] else "still gap"
        print(f"[{flag}] {r['query_id']} ({r['domain']}) -> {r['top_doc']} ({r['top_score']})")

    out = {"n_total": n_total, "n_above_threshold": n_above, "per_query": results}
    out_path = RESULTS_DIR / "kb_expansion_coverage_check.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
