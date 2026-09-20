"""Track E, step 3: does reflection actually help, or is it just slower?

Joins this track's own funnel_trace.csv (reflection_count, wall_clock_seconds
per ticket) against Track C's already-real judge_overall_score
(../../Track-C-Response-Quality/results/clario_full_graph_drafts.csv) on
query_id, then compares reflected tickets (reflection_count > 0) against
non-reflected tickets on both quality and latency.

Deliberately does NOT use Testing/04's load-test latency numbers, even
though the original proposal named that file - those numbers come from
synthetic concurrent-load tickets, not these 70 real ones, and matching
"reflected vs not" needs to be done on the same tickets whose latency and
quality were both measured in the same run. This track's own
wall_clock_seconds (captured in run_funnel_trace.py) is the real, matched
number for that; Testing/04 is cited in the report as separate context,
not blended into this comparison.

Statistical note: the proposal calls for a paired test (McNemar's / paired
t / Wilcoxon signed-rank) for before/after comparisons - but reflected and
non-reflected tickets are two different, independent groups of tickets,
not the same tickets measured twice, so there is nothing to pair. The
correct test for two independent groups on a score that isn't guaranteed
normal (a 1-5 judge score) is the Mann-Whitney U test, used here instead -
this is a real methodological correction from the original plan, not
the plan being followed loosely.

Usage:
    python3 compute_reflection_value.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from scipy.stats import mannwhitneyu

_HERE = Path(__file__).resolve().parent
E_RESULTS = _HERE.parent / "results"
C_RESULTS = _HERE.parent.parent / "Track-C-Response-Quality" / "results"


def to_bool(v: str) -> bool:
    return str(v).strip().lower() == "true"


def main() -> None:
    with open(E_RESULTS / "funnel_trace.csv", newline="", encoding="utf-8-sig") as f:
        trace = {r["query_id"]: r for r in csv.DictReader(f) if not r.get("error")}

    with open(C_RESULTS / "clario_full_graph_drafts.csv", newline="", encoding="utf-8-sig") as f:
        draft_rows = list(csv.DictReader(f))

    # a ticket can have >1 domain-draft row (dual-domain); average its judge score per ticket
    scores_by_ticket: dict[str, list[float]] = {}
    for r in draft_rows:
        if not r.get("judge_overall_score"):
            continue
        scores_by_ticket.setdefault(r["query_id"], []).append(float(r["judge_overall_score"]))

    reflected_scores, non_reflected_scores = [], []
    reflected_latency, non_reflected_latency = [], []
    matched = 0

    for qid, t in trace.items():
        judge_scores = scores_by_ticket.get(qid)
        latency = float(t["wall_clock_seconds"])
        was_reflected = int(t["reflection_count"] or 0) > 0
        if was_reflected:
            reflected_latency.append(latency)
        else:
            non_reflected_latency.append(latency)
        if judge_scores is None:
            continue  # ticket escalated before any specialist ran - no quality score to compare
        matched += 1
        mean_score = sum(judge_scores) / len(judge_scores)
        (reflected_scores if was_reflected else non_reflected_scores).append(mean_score)

    def describe(xs: list[float]) -> dict:
        if not xs:
            return {"n": 0}
        return {"n": len(xs), "mean": round(statistics.mean(xs), 3),
                "median": round(statistics.median(xs), 3),
                "stdev": round(statistics.stdev(xs), 3) if len(xs) > 1 else 0.0}

    result = {
        "n_tickets_with_a_quality_score": matched,
        "quality_score": {"reflected": describe(reflected_scores), "non_reflected": describe(non_reflected_scores)},
        "latency_seconds": {"reflected": describe(reflected_latency), "non_reflected": describe(non_reflected_latency)},
    }

    if reflected_scores and non_reflected_scores:
        u_stat, p_value = mannwhitneyu(reflected_scores, non_reflected_scores, alternative="two-sided")
        result["quality_mann_whitney_u"] = {"u": round(float(u_stat), 2), "p_value": round(float(p_value), 4)}
    if reflected_latency and non_reflected_latency:
        u_stat, p_value = mannwhitneyu(reflected_latency, non_reflected_latency, alternative="two-sided")
        result["latency_mann_whitney_u"] = {"u": round(float(u_stat), 2), "p_value": round(float(p_value), 4)}

    print(json.dumps(result, indent=2))
    with open(E_RESULTS / "reflection_value_summary.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {E_RESULTS / 'reflection_value_summary.json'}")


if __name__ == "__main__":
    main()
