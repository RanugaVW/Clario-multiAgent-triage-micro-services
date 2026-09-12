"""Track D, step 3: once both humans have filled in
data/judge_calibration_sample.csv, run this to check (a) whether the two
humans agree with each other, and (b) whether the automatic judge agrees
with them - per DATA_SCIENCE_EVALUATION_PROPOSAL.md §7.4 steps 3-4.

Step 3 (human-vs-human): weighted Cohen's kappa per score category, on the
two humans' raw 1-5 scores.

Step 4 (judge-vs-humans): the two humans' scores are combined by taking
their mean, rounded to the nearest integer 1-5 (kept as a float for the
Spearman correlation, which doesn't need integers). The automatic judge's
score for the same pair (read from data/judge_calibration_answer_key.csv,
joined on pair_id) is compared against that combined human score using
both weighted kappa (rounded) and Spearman correlation (unrounded mean),
exactly as the proposal specifies.

This script only computes numbers - it does not decide whether the result
counts as "good enough"; state that judgment in the report, not here,
and alongside the sample-size caveat the proposal states outright (25-30
pairs support a general statement, not a tight confidence interval).

Usage:
    python3 compute_agreement.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import cohen_kappa_score

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
SAMPLE_PATH = DATA_DIR / "judge_calibration_sample.csv"
KEY_PATH = DATA_DIR / "judge_calibration_answer_key.csv"

CATEGORIES = [
    "overall_score", "priority_tone_match_score", "completeness_score",
    "accuracy_score", "policy_compliance_score", "groundedness_score",
]


def load_rows() -> tuple[list[dict], dict[str, dict]]:
    with open(SAMPLE_PATH, newline="", encoding="utf-8-sig") as f:
        sample = list(csv.DictReader(f))
    with open(KEY_PATH, newline="", encoding="utf-8-sig") as f:
        key = {row["pair_id"]: row for row in csv.DictReader(f)}
    return sample, key


def to_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        n = int(round(float(value)))
    except ValueError:
        return None
    return max(1, min(5, n))


def main() -> None:
    sample, key = load_rows()

    incomplete = [
        r["pair_id"] for r in sample
        if any(to_int(r.get(f"human1_{c}")) is None or to_int(r.get(f"human2_{c}")) is None for c in CATEGORIES)
    ]
    if incomplete:
        print(f"{len(incomplete)} of {len(sample)} pairs are missing at least one human score "
              f"(pair_ids: {', '.join(incomplete[:10])}{'...' if len(incomplete) > 10 else ''}).")
        print("Fill in every human1_*/human2_* column in judge_calibration_sample.csv before running this.")
        return

    print(f"All {len(sample)} pairs fully scored by both humans. Computing agreement.\n")

    print("=== Step 3: human vs human (weighted Cohen's kappa) ===")
    h1h2_kappas = {}
    for cat in CATEGORIES:
        h1 = [to_int(r[f"human1_{cat}"]) for r in sample]
        h2 = [to_int(r[f"human2_{cat}"]) for r in sample]
        kappa = cohen_kappa_score(h1, h2, weights="linear", labels=[1, 2, 3, 4, 5])
        h1h2_kappas[cat] = kappa
        print(f"  {cat}: kappa={kappa:.3f}")
    print(f"  mean across categories: {sum(h1h2_kappas.values()) / len(h1h2_kappas):.3f}\n")

    print("=== Step 4: automatic judge vs combined human score ===")
    judge_kappas, judge_spearmans = {}, {}
    for cat in CATEGORIES:
        judge_key = f"judge_{cat}"
        judge_scores, human_means_rounded, human_means_raw = [], [], []
        for r in sample:
            k = key.get(r["pair_id"])
            if k is None or not k.get(judge_key):
                continue
            h1 = to_int(r[f"human1_{cat}"])
            h2 = to_int(r[f"human2_{cat}"])
            mean = (h1 + h2) / 2
            human_means_raw.append(mean)
            human_means_rounded.append(int(round(mean)))
            judge_scores.append(to_int(k[judge_key]))

        kappa = cohen_kappa_score(judge_scores, human_means_rounded, weights="linear", labels=[1, 2, 3, 4, 5])
        rho, _ = spearmanr(judge_scores, human_means_raw)
        judge_kappas[cat] = kappa
        judge_spearmans[cat] = rho
        print(f"  {cat}: kappa={kappa:.3f}, spearman={rho:.3f} (n={len(judge_scores)})")

    print(f"  mean kappa across categories: {sum(judge_kappas.values()) / len(judge_kappas):.3f}")
    print(f"  mean spearman across categories: {sum(judge_spearmans.values()) / len(judge_spearmans):.3f}")

    print(f"\nSample size: {len(sample)} pairs. Per the proposal's own limit (ARES used ~150 pairs to "
          f"calibrate its judge): this supports a general statement about agreement, not a precise, "
          f"tightly-bounded number.")


if __name__ == "__main__":
    main()
