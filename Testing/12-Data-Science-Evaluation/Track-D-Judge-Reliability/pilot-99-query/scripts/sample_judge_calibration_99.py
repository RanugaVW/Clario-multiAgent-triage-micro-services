"""Track D PILOT, step 2: prepare the 99-query batch for two-human scoring.

Same shape as ../../scripts/sample_judge_calibration.py, pointed at the
pilot's own results/data files. Defaults to including ALL rows (not a
stratified sub-sample) - the same choice made for the 70-real-ticket round,
since this pilot's whole purpose is finding any remaining judge gaps before
trusting the real-ticket round, and a full pass finds more of them than a
smaller sample would. Pass --n to take a smaller stratified sample instead
if the full set turns out to be too much scoring work.

Usage:
    python3 sample_judge_calibration_99.py [--n 99] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DATA_DIR = _HERE.parent / "data"
DRAFTS_PATH = RESULTS_DIR / "clario_drafts_and_judge_scores_99.csv"

HUMAN_SCORE_COLUMNS = [
    "overall_score", "priority_tone_match_score", "completeness_score",
    "accuracy_score", "policy_compliance_score", "groundedness_score",
]


def load_drafts() -> list[dict]:
    with open(DRAFTS_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def stratified_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    if n >= len(rows):
        rng = random.Random(seed)
        picked = list(rows)
        rng.shuffle(picked)
        return picked

    rng = random.Random(seed)
    by_domain: dict[str, list[dict]] = {}
    for r in rows:
        by_domain.setdefault(r["domain_drafted"], []).append(r)
    for bucket in by_domain.values():
        rng.shuffle(bucket)

    domains = sorted(by_domain, key=lambda d: len(by_domain[d]))
    picked: list[dict] = []
    if "hr" in by_domain:
        picked += by_domain["hr"][: min(3, len(by_domain["hr"]))]

    remaining_slots = n - len(picked)
    other_domains = [d for d in domains if d != "hr"]
    total_other = sum(len(by_domain[d]) for d in other_domains)
    for d in other_domains:
        share = round(remaining_slots * len(by_domain[d]) / total_other) if total_other else 0
        already_taken = sum(1 for p in picked if p["domain_drafted"] == d)
        take = min(share, len(by_domain[d]) - already_taken)
        picked += [row for row in by_domain[d] if row not in picked][:take]

    picked_ids = {(r["query_id"], r["domain_drafted"]) for r in picked}
    if len(picked) < n:
        for r in rows:
            if len(picked) >= n:
                break
            key = (r["query_id"], r["domain_drafted"])
            if key not in picked_ids:
                picked.append(r)
                picked_ids.add(key)
    picked = picked[:n]
    rng.shuffle(picked)
    return picked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=99, help="Sample size (default: all rows)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = load_drafts()
    sample = stratified_sample(rows, args.n, args.seed)

    counts: dict[str, int] = {}
    for r in sample:
        counts[r["domain_drafted"]] = counts.get(r["domain_drafted"], 0) + 1
    print(f"Sampled {len(sample)} pairs: {counts}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sample_path = DATA_DIR / "judge_calibration_sample_99.csv"
    sample_fields = [
        "pair_id", "query_id", "domain_drafted", "priority", "ticket_text_note",
        "draft", "retrieved_sources",
    ] + [f"human1_{c}" for c in HUMAN_SCORE_COLUMNS] + ["human1_notes"] \
      + [f"human2_{c}" for c in HUMAN_SCORE_COLUMNS] + ["human2_notes"]
    with open(sample_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sample_fields)
        writer.writeheader()
        for i, r in enumerate(sample, start=1):
            writer.writerow({
                "pair_id": f"P{i:03d}",
                "query_id": r["query_id"],
                "domain_drafted": r["domain_drafted"],
                "priority": r["priority"],
                "ticket_text_note": "See Track-A-Retrieval-Quality/data/retrieval_ground_truth.csv for this query_id's ticket text",
                "draft": r["draft"],
                "retrieved_sources": r["retrieved_sources"],
                **{f"human1_{c}": "" for c in HUMAN_SCORE_COLUMNS}, "human1_notes": "",
                **{f"human2_{c}": "" for c in HUMAN_SCORE_COLUMNS}, "human2_notes": "",
            })

    key_path = DATA_DIR / "judge_calibration_answer_key_99.csv"
    with open(key_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pair_id", "query_id", "domain_drafted",
            "judge_overall_score", "judge_priority_tone_match_score", "judge_completeness_score",
            "judge_accuracy_score", "judge_policy_compliance_score", "judge_groundedness_score",
            "judge_reasoning", "judge_model",
        ])
        writer.writeheader()
        for i, r in enumerate(sample, start=1):
            writer.writerow({
                "pair_id": f"P{i:03d}",
                "query_id": r["query_id"],
                "domain_drafted": r["domain_drafted"],
                "judge_overall_score": r["judge_overall_score"],
                "judge_priority_tone_match_score": r["judge_priority_tone_match_score"],
                "judge_completeness_score": r["judge_completeness_score"],
                "judge_accuracy_score": r["judge_accuracy_score"],
                "judge_policy_compliance_score": r["judge_policy_compliance_score"],
                "judge_groundedness_score": r["judge_groundedness_score"],
                "judge_reasoning": r["judge_reasoning"],
                "judge_model": r["judge_model"],
            })

    print(f"Wrote {len(sample)} rows to {sample_path} (for the two humans to fill in)")
    print(f"Wrote the judge's own scores for the same rows to {key_path} (kept separate - don't show this to the raters)")


if __name__ == "__main__":
    main()
