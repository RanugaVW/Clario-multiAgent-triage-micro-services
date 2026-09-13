"""Track C PILOT, step 1: run every one of Track A's 99 queries through the
REAL, complete LangGraph pipeline (classification -> routing -> specialist
draft -> validation/reflection -> judge -> escalation), exactly the path a
live ticket takes, and save the result.

This deliberately does NOT reuse Track D's already-generated
pilot-99-query/results/clario_drafts_and_judge_scores_99.csv, even though
it looks like the same data. Track D's generator explicitly BYPASSES
classification_node and routing_node (see its own README) to isolate
"does the judge agree with a human" from routing correctness. Track C is
the opposite: it exists to check the real end-to-end reply a customer
would actually receive, so it has to go through the same graph a live
ticket goes through, routing mistakes and all. Track B's fixes to
routing_node.py/escalation_node.py this session make this run meaningfully
different from what it would have produced before those fixes.

A ticket that gets escalated (e.g. every "hr"-routed ticket, per current
policy) still gets scored here - agent_drafts is populated by the
specialist before escalation_node ever runs, so "this ticket would have
escalated instead of auto-sending" and "here's how good the underlying
draft was" are two separate, both-interesting facts, not a contradiction.

Usage:
    python3 run_full_graph_generation_99.py [--start N] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[5] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.graph.graph_builder import build_graph  # noqa: E402

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent.parent.parent / "Track-A-Retrieval-Quality" / "data"
GT_PATH = DATA_DIR / "retrieval_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

# Gemini free-tier pacing, same fix and same reasoning as Track D's
# generate_clario_drafts_99.py: draft generation + judging share one
# model's 15-req/min budget, and each ticket costs several calls
# (classification is local, but retrieval/drafting/judging/reflection are
# not) - unpaced runs hit 429 RESOURCE_EXHAUSTED by ticket ~20.
PACING_SECONDS = 8


def _build_initial_state(ticket_id: str, raw_text: str) -> dict:
    """Mirrors app/main.py's process_ticket initial_state and
    run_pairwise_evaluation.py's _build_initial_state exactly, so this run
    behaves identically to a real incoming ticket."""
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
    if limit:
        rows = rows[start:start + limit]
    else:
        rows = rows[start:]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "clario_full_graph_drafts_99.csv"
    fieldnames = [
        "query_id", "gt_domain", "routing_decision", "domain_drafted", "category",
        "priority", "sentiment", "confidence", "escalation_triggered", "escalation_reasons",
        "draft", "retrieved_sources", "judge_overall_score", "judge_priority_tone_match_score",
        "judge_completeness_score", "judge_accuracy_score", "judge_policy_compliance_score",
        "judge_groundedness_score", "judge_reasoning",
    ]
    write_header = not out_path.exists()
    processed = failed = skipped = 0

    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i, row in enumerate(rows, start=1):
            qid, text, gt_domain = row["query_id"], row["query_text"], row["domain"]
            print(f"[{i}/{len(rows)}] {qid}: {text[:70]}", flush=True)
            try:
                final_state = await asyncio.wait_for(
                    graph.ainvoke(_build_initial_state(qid, text)), timeout=180,
                )
            except Exception as e:
                print(f"  FAILED: {e}", flush=True)
                failed += 1
                time.sleep(PACING_SECONDS)
                continue

            drafts = final_state.get("agent_drafts") or {}
            if not drafts:
                print("  no draft produced (escalated before any specialist ran) - recording routing only", flush=True)
                writer.writerow({
                    "query_id": qid, "gt_domain": gt_domain,
                    "routing_decision": final_state.get("routing_decision"),
                    "domain_drafted": "", "category": final_state.get("category"),
                    "priority": final_state.get("priority"), "sentiment": final_state.get("sentiment"),
                    "confidence": final_state.get("classification_confidence"),
                    "escalation_triggered": final_state.get("escalation_triggered"),
                    "escalation_reasons": ";".join(final_state.get("escalation_reasons") or []),
                    "draft": "", "retrieved_sources": "", "judge_overall_score": "",
                    "judge_priority_tone_match_score": "", "judge_completeness_score": "",
                    "judge_accuracy_score": "", "judge_policy_compliance_score": "",
                    "judge_groundedness_score": "", "judge_reasoning": "",
                })
                skipped += 1
                f.flush()
                time.sleep(PACING_SECONDS)
                continue

            judge_evals = final_state.get("judge_evaluations") or {}
            retrieved = final_state.get("retrieved_context") or {}
            for domain, draft in drafts.items():
                if not draft:
                    continue
                judge = judge_evals.get(domain, {})
                sources = retrieved.get(domain, [])
                writer.writerow({
                    "query_id": qid, "gt_domain": gt_domain,
                    "routing_decision": final_state.get("routing_decision"),
                    "domain_drafted": domain, "category": final_state.get("category"),
                    "priority": final_state.get("priority"), "sentiment": final_state.get("sentiment"),
                    "confidence": final_state.get("classification_confidence"),
                    "escalation_triggered": final_state.get("escalation_triggered"),
                    "escalation_reasons": ";".join(final_state.get("escalation_reasons") or []),
                    "draft": draft,
                    "retrieved_sources": json.dumps([s.get("text", "") for s in sources]),
                    "judge_overall_score": judge.get("overall_score", ""),
                    "judge_priority_tone_match_score": judge.get("priority_tone_match_score", ""),
                    "judge_completeness_score": judge.get("completeness_score", ""),
                    "judge_accuracy_score": judge.get("accuracy_score", ""),
                    "judge_policy_compliance_score": judge.get("policy_compliance_score", ""),
                    "judge_groundedness_score": judge.get("groundedness_score", ""),
                    "judge_reasoning": judge.get("reasoning", ""),
                })
                processed += 1
            f.flush()
            time.sleep(PACING_SECONDS)

    print(f"\nDone: {processed} domain-drafts written, {skipped} escalated-before-drafting, {failed} failed.")
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=0, help="Row index to start from (for resuming)")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process this run")
    args = parser.parse_args()
    asyncio.run(run(args.start, args.limit))


if __name__ == "__main__":
    main()
