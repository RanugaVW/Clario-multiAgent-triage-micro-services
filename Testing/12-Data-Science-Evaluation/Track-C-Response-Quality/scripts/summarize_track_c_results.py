"""Track C FINAL, step 6: combine all four checks (pairwise win-rate,
absolute judge score, semantic similarity, groundedness) into one
per-domain report - the numbers TRACK_C_CONCLUSION.md is built from.

Reads whatever of the four result files already exist and reports on
those, printing a clear note for any that are missing rather than
failing, since these are meant to be run and reviewed incrementally
(the proposal explicitly treats them as four separate checks).

Usage:
    python3 summarize_track_c_results.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts.csv"
PAIRWISE_PATH = RESULTS_DIR / "pairwise_results.csv"
SIMILARITY_PATH = RESULTS_DIR / "semantic_similarity.csv"
GROUNDEDNESS_PATH = RESULTS_DIR / "groundedness.csv"

SCORE_FIELDS = [
    "judge_overall_score", "judge_priority_tone_match_score", "judge_completeness_score",
    "judge_accuracy_score", "judge_policy_compliance_score", "judge_groundedness_score",
]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> None:
    print("=" * 70)
    print("TRACK C - FINAL RESPONSE QUALITY, 70 REAL TICKETS")
    print("=" * 70)

    if DRAFTS_PATH.exists():
        with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
            all_rows = list(csv.DictReader(f))
        drafted = [r for r in all_rows if r["draft"].strip()]
        by_domain: dict[str, list[dict]] = defaultdict(list)
        for r in drafted:
            by_domain[r["domain_drafted"]].append(r)

        print(f"\n--- Check 2: Absolute judge score ({len(drafted)} domain-drafts, "
              f"{len(all_rows) - len(drafted)} escalated before drafting) ---")
        for domain in sorted(by_domain):
            rows = by_domain[domain]
            print(f"\n{domain} (n={len(rows)}):")
            for field in SCORE_FIELDS:
                values = [float(r[field]) for r in rows if r[field]]
                m = mean(values)
                print(f"  {field}: {m:.2f}" if m is not None else f"  {field}: no data")
    else:
        print(f"\n--- Check 2: Absolute judge score --- NOT YET RUN (missing {DRAFTS_PATH.name}) ---")

    if PAIRWISE_PATH.exists():
        with open(PAIRWISE_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_domain_p: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_domain_p[r["domain"]].append(r)
        print(f"\n--- Check 1: Pairwise win-rate vs real human reply ({len(rows)} comparisons) ---")
        for domain in sorted(by_domain_p):
            drows = by_domain_p[domain]
            counts: dict[str, int] = defaultdict(int)
            for r in drows:
                counts[r["final_winner"]] += 1
            print(f"{domain} (n={len(drows)}): {dict(counts)}")
    else:
        print(f"\n--- Check 1: Pairwise win-rate --- NOT YET RUN (missing {PAIRWISE_PATH.name} - "
              f"see ../README.md for the run_pairwise_evaluation.py + export_pairwise_from_supabase.py steps) ---")

    if SIMILARITY_PATH.exists():
        with open(SIMILARITY_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_domain_s: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_domain_s[r["domain_drafted"]].append(r)
        print(f"\n--- Check 3: Semantic similarity vs real human reply ({len(rows)} scored) ---")
        for domain in sorted(by_domain_s):
            drows = by_domain_s[domain]
            cos_vals = [float(r["minilm_cosine_as_sent"]) for r in drows]
            print(f"{domain} (n={len(drows)}): mean MiniLM cosine (vs as-sent) = {mean(cos_vals):.3f}")
    else:
        print(f"\n--- Check 3: Semantic similarity --- NOT YET RUN (missing {SIMILARITY_PATH.name}) ---")

    if GROUNDEDNESS_PATH.exists():
        with open(GROUNDEDNESS_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_domain_g: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_domain_g[r["domain_drafted"]].append(r)
        print(f"\n--- Check 4: Groundedness (sentence-level) ---")
        for domain in sorted(by_domain_g):
            drows = by_domain_g[domain]
            supported = sum(1 for r in drows if r["supported"] == "True")
            print(f"{domain}: {supported}/{len(drows)} sentences supported ({100 * supported / len(drows):.1f}%)")
    else:
        print(f"\n--- Check 4: Groundedness --- NOT YET RUN (missing {GROUNDEDNESS_PATH.name}) ---")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
