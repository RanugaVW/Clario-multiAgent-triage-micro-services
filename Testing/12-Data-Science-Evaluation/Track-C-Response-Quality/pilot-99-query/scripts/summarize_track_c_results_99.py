"""Track C PILOT, step 3: combine the absolute judge scores (already in
clario_full_graph_drafts_99.csv) and the groundedness check (groundedness_99.csv)
into one per-domain summary - the pilot's version of "did the whole
pipeline work end to end," not a result to present on its own (there's no
human reference for the 99-query set, so pairwise win-rate and semantic
similarity can't be computed here - see ../README.md).

Usage:
    python3 summarize_track_c_results_99.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts_99.csv"
GROUNDEDNESS_PATH = RESULTS_DIR / "groundedness_99.csv"

SCORE_FIELDS = [
    "judge_overall_score", "judge_priority_tone_match_score", "judge_completeness_score",
    "judge_accuracy_score", "judge_policy_compliance_score", "judge_groundedness_score",
]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> None:
    if not DRAFTS_PATH.exists():
        print(f"{DRAFTS_PATH} not found - run run_full_graph_generation_99.py first.")
        return

    with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["draft"].strip()]
    n_escalated_before_draft = 0
    with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
        n_escalated_before_draft = sum(1 for r in csv.DictReader(f) if not r["draft"].strip())

    by_domain: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_domain[r["domain_drafted"]].append(r)

    print(f"=== Absolute judge scores by domain ({len(rows)} domain-drafts, "
          f"{n_escalated_before_draft} escalated before any specialist drafted) ===\n")
    for domain in sorted(by_domain):
        domain_rows = by_domain[domain]
        print(f"{domain} (n={len(domain_rows)}):")
        for field in SCORE_FIELDS:
            values = [float(r[field]) for r in domain_rows if r[field]]
            m = mean(values)
            print(f"  {field}: {m:.2f}" if m is not None else f"  {field}: no data")
        print()

    if GROUNDEDNESS_PATH.exists():
        with open(GROUNDEDNESS_PATH, newline="", encoding="utf-8") as f:
            g_rows = list(csv.DictReader(f))
        by_domain_g: dict[str, list[dict]] = defaultdict(list)
        for r in g_rows:
            by_domain_g[r["domain_drafted"]].append(r)
        print("=== Groundedness (sentence-level, mechanical check) by domain ===\n")
        for domain in sorted(by_domain_g):
            domain_rows = by_domain_g[domain]
            supported = sum(1 for r in domain_rows if r["supported"] == "True")
            print(f"{domain}: {supported}/{len(domain_rows)} sentences supported "
                  f"({100 * supported / len(domain_rows):.1f}%)")
    else:
        print(f"({GROUNDEDNESS_PATH.name} not found yet - run compute_groundedness_99.py first)")

    print("\nThis pilot round exists to catch pipeline problems (full-graph run failures, "
          "response_judge.py regressions, a broken groundedness script) before spending real "
          "effort/API cost on the 70-ticket round - it has no human reference to score against, "
          "so pairwise win-rate and semantic similarity are not computed here.")


if __name__ == "__main__":
    main()
