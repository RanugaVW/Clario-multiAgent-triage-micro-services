"""Track E, step 2: turn results/funnel_trace.csv into the four funnel rates
the proposal asks for (cache-hit, reflection-loop, misroute-retry, escalation),
each with a 95% Wilson confidence interval - the proposal's own reason for
using Wilson over a plain percentage: several groups here are small (the
funnel runs on all 70 tickets, but any one routing class or domain slice
inside it can still be under 30), and a bare percentage overstates precision
on a small n.

Wilson's interval is implemented directly (closed-form) rather than pulling
in statsmodels for one formula - same number statsmodels' proportion_confint
returns for method="wilson", just without the extra dependency.

Usage:
    python3 compute_funnel_rates.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
TRACE_PATH = RESULTS_DIR / "funnel_trace.csv"

Z_95 = 1.959963984540054  # two-sided 95% normal quantile


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float, float]:
    """Returns (point_estimate, lower, upper), all as proportions 0-1."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) / n) + (z ** 2 / (4 * n ** 2)))) / denom
    return p, max(0.0, center - margin), min(1.0, center + margin)


def to_bool(v: str) -> bool:
    return str(v).strip().lower() == "true"


def main() -> None:
    with open(TRACE_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    scored = [r for r in rows if not r.get("error")]
    n = len(scored)
    failed = [r for r in rows if r.get("error")]

    cache_hits = sum(1 for r in scored if to_bool(r["cache_hit"]))
    reflected = sum(1 for r in scored if int(r["reflection_count"] or 0) > 0)
    misroute_retried = sum(1 for r in scored if to_bool(r["reroute_attempted"]))
    escalated = sum(1 for r in scored if to_bool(r["escalation_triggered"]))

    funnel = {}
    for name, count in [
        ("cache_hit_rate", cache_hits),
        ("reflection_loop_rate", reflected),
        ("misroute_retry_rate", misroute_retried),
        ("escalation_rate", escalated),
    ]:
        p, lo, hi = wilson_interval(count, n)
        funnel[name] = {"count": count, "n": n, "point": round(p, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4)}

    # failure_type breakdown, among tickets that reached validation (n excludes early-escalation, no-signal routes)
    failure_counts: dict[str, int] = {}
    for r in scored:
        ft = r.get("failure_type") or "none"
        failure_counts[ft] = failure_counts.get(ft, 0) + 1

    summary = {
        "n_scored": n,
        "n_failed_to_run": len(failed),
        "funnel_rates": funnel,
        "failure_type_counts": failure_counts,
        "note": "n=70 real tickets, one pass each, live full pipeline. "
                "A CI this wide on n=70 is expected and reported, not smoothed over - "
                "see the proposal's own point that under ~30 examples per group, "
                "a bare percentage overstates precision.",
    }
    print(json.dumps(summary, indent=2))
    with open(RESULTS_DIR / "funnel_rates_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {RESULTS_DIR / 'funnel_rates_summary.json'}")


if __name__ == "__main__":
    main()
