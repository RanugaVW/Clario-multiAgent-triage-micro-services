"""Track E, step 3 verification (v5) - the full-scale check. v4 targeted only
the 15 ticket IDs already known to reflect, cheaply, to check the critique
fix (validation_node.py's llm_judge_check now names the specific failed
check instead of the constant string "local_heuristic_judge") before
committing to a full re-run. This script processes all 70 tickets - a
properly-sized sample, not a targeted subset - to get a real answer on
whether that fix's effect holds up, rather than resting the conclusion on
n=13.

Usage:
    python3 compute_reflection_value_v5.py
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
    with open(RESULTS_DIR / "funnel_trace_v5.csv", newline="", encoding="utf-8-sig") as f:
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
        "n_tickets_run": len(rows),
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
    with open(RESULTS_DIR / "reflection_value_summary_v5.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'reflection_value_summary_v5.json'}")


if __name__ == "__main__":
    main()
