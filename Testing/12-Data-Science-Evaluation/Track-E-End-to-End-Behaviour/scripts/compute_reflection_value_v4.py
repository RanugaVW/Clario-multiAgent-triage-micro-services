"""Track E, step 2 verification (v4) - checks whether the critique-quality fix
(validation_node.py's llm_judge_check now names the specific failed check
instead of the constant string "local_heuristic_judge") actually moves the
paired before/after reflection score, on top of v3's already-verified
fallback fix.

This run targeted only the 15 ticket IDs v3's clean run confirmed reflect
(see run_funnel_trace_v4.py) rather than the full 70, to check this one
fix cheaply before deciding whether a full re-run is worth the shared daily
API quota. Two of those 15 (Q021, Q030) did not reflect this time - judge
sampling is randomized (decide_judge_call), so which tickets reflect drifts
run to run, already documented in the report - leaving 13 paired tickets
here, all correctly excluded rather than padded.

Usage:
    python3 compute_reflection_value_v4.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from scipy.stats import wilcoxon

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"


def main() -> None:
    with open(RESULTS_DIR / "funnel_trace_v4.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    pairs = []
    for r in rows:
        if r.get("error") or not r.get("pre_reflection_judge_score_mean") or not r.get("final_judge_score_mean"):
            continue
        pairs.append({
            "query_id": r["query_id"],
            "pre": float(r["pre_reflection_judge_score_mean"]),
            "final": float(r["final_judge_score_mean"]),
        })

    pre_scores = [p["pre"] for p in pairs]
    final_scores = [p["final"] for p in pairs]
    deltas = [p["final"] - p["pre"] for p in pairs]

    improved = sum(1 for d in deltas if d > 0)
    unchanged = sum(1 for d in deltas if d == 0)
    worsened = sum(1 for d in deltas if d < 0)

    result = {
        "n_reflected_with_paired_scores": len(pairs),
        "n_targeted": 15,
        "n_did_not_reflect_this_run": 15 - len(pairs),
        "pre_reflection_score": {"mean": round(statistics.mean(pre_scores), 3), "median": round(statistics.median(pre_scores), 3)},
        "final_score": {"mean": round(statistics.mean(final_scores), 3), "median": round(statistics.median(final_scores), 3)},
        "mean_delta": round(statistics.mean(deltas), 3),
        "tickets_improved": improved,
        "tickets_unchanged": unchanged,
        "tickets_worsened": worsened,
        "per_ticket": pairs,
    }

    non_zero = [d for d in deltas if d != 0]
    if len(non_zero) >= 1:
        stat, p_value = wilcoxon(pre_scores, final_scores)
        result["wilcoxon_signed_rank"] = {"statistic": round(float(stat), 2), "p_value": round(float(p_value), 4)}
    else:
        result["wilcoxon_signed_rank"] = None

    print(json.dumps({k: v for k, v in result.items() if k != "per_ticket"}, indent=2))
    with open(RESULTS_DIR / "reflection_value_summary_v4.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'reflection_value_summary_v4.json'}")


if __name__ == "__main__":
    main()
