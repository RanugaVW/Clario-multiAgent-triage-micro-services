"""Track D PILOT, step 3: same computation as ../../scripts/compute_agreement.py,
pointed at the 99-query pilot's own sample/answer-key files. Run once both
humans have filled in data/judge_calibration_sample_99.csv.

Usage:
    python3 compute_agreement_99.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import cohen_kappa_score

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
SAMPLE_PATH = DATA_DIR / "judge_calibration_sample_99.csv"
KEY_PATH = DATA_DIR / "judge_calibration_answer_key_99.csv"

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
        print("Fill in every human1_*/human2_* column in judge_calibration_sample_99.csv before running this.")
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

    print(f"\nSample size: {len(sample)} pairs. This is the pilot round on the 99-query set - run "
          f"BEFORE the real-ticket round (see ../../README.md) specifically to catch judge gaps a "
          f"single dataset's fixes might miss. A weak result here means back to response_judge.py, "
          f"not straight to scoring the 70-ticket set.")


if __name__ == "__main__":
    main()
