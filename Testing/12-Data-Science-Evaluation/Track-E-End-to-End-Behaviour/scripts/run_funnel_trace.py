"""Track E, step 1: run the real, full LangGraph pipeline over the same 70
real tickets Tracks A-D already used, capturing the pipeline-funnel state
that no earlier track recorded: cache_hit, reflection_count, failure_type,
needs_reroute/reroute_attempted, and wall-clock latency per ticket.

This deliberately does NOT re-capture drafts, retrieved sources, or judge
scores - that data already exists in
../../Track-C-Response-Quality/results/clario_full_graph_drafts.csv from
today's real run. Re-running the same graph a second time is still a real,
separate live pass (funnel state isn't persisted anywhere from the first
run), but this script only needs to keep the lightweight flags, not
duplicate the heavy text/score output Track C already has.

Reuses build_graph() and the same ground truth Track A/B/C already use
(../../Track-A-Retrieval-Quality/data/lms_ticket_ground_truth.csv), so
funnel rates here describe the exact same 70 tickets the rest of the
evaluation is built on - not a different sample.

Usage:
    python3 run_funnel_trace.py [--start N] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.graph.graph_builder import build_graph  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parent.parent / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

PACING_SECONDS = 8  # same Gemini free-tier reasoning every other generation script in this project uses


def _build_initial_state(ticket_id: str, raw_text: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "raw_text": raw_text,
        "reflection_count": 0,
        "reflection_critiques": [],
        "reroute_attempted": False,
        "needs_reroute": False,
        "agent_drafts": {},
        "retrieved_context": {},
        "rag_top_score": {},
        "low_relevance_flags": {},
        "validation_result": {},
    }


def load_queries() -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


async def run(start: int, limit: int | None) -> None:
    graph = build_graph()
    rows = load_queries()
    rows = rows[start:start + limit] if limit else rows[start:]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "funnel_trace.csv"
    fieldnames = [
        "query_id", "gt_domain", "routing_decision", "classification_confidence",
        "cache_hit", "reflection_count", "failure_type", "needs_reroute", "reroute_attempted",
        "escalation_triggered", "escalation_reasons", "wall_clock_seconds", "error",
    ]
    write_header = not out_path.exists()
    processed = failed = 0

    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i, row in enumerate(rows, start=1):
            qid, text, gt_domain = row["query_id"], row["query_text"], row["domain"]
            print(f"[{i}/{len(rows)}] {qid}: {text[:70]}", flush=True)
            t0 = time.perf_counter()
            try:
                final_state = await asyncio.wait_for(
                    graph.ainvoke(_build_initial_state(qid, text)), timeout=180,
                )
                elapsed = time.perf_counter() - t0
            except Exception as e:
                elapsed = time.perf_counter() - t0
                print(f"  FAILED after {elapsed:.1f}s: {e}", flush=True)
                writer.writerow({
                    "query_id": qid, "gt_domain": gt_domain, "routing_decision": "",
                    "classification_confidence": "", "cache_hit": "", "reflection_count": "",
                    "failure_type": "", "needs_reroute": "", "reroute_attempted": "",
                    "escalation_triggered": "", "escalation_reasons": "",
                    "wall_clock_seconds": f"{elapsed:.2f}", "error": str(e)[:200],
                })
                failed += 1
                f.flush()
                time.sleep(PACING_SECONDS)
                continue

            writer.writerow({
                "query_id": qid,
                "gt_domain": gt_domain,
                "routing_decision": final_state.get("routing_decision"),
                "classification_confidence": final_state.get("classification_confidence"),
                "cache_hit": final_state.get("cache_hit", False),
                "reflection_count": final_state.get("reflection_count", 0),
                "failure_type": final_state.get("failure_type", "none"),
                "needs_reroute": final_state.get("needs_reroute", False),
                "reroute_attempted": final_state.get("reroute_attempted", False),
                "escalation_triggered": final_state.get("escalation_triggered", False),
                "escalation_reasons": ";".join(final_state.get("escalation_reasons") or []),
                "wall_clock_seconds": f"{elapsed:.2f}",
                "error": "",
            })
            processed += 1
            f.flush()
            time.sleep(PACING_SECONDS)

    print(f"\nDone: {processed} processed, {failed} failed.")
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.start, args.limit))


if __name__ == "__main__":
    main()
