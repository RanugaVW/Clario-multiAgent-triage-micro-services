"""Track C FINAL, step 2: same as
../pilot-99-query/scripts/run_full_graph_generation_99.py, pointed at the
70 real tickets. Run ../pilot-99-query/ first (see ../README.md) - only
run this once that pilot comes back clean.

This produces the SAME shape of local CSV as the pilot for the absolute-
score and groundedness checks. It does NOT replace
scripts/run_pairwise_evaluation.py (the existing, Supabase-backed pairwise
comparison script the proposal names directly) - that script also runs
every ticket through the real graph itself, so running both means every
ticket goes through the graph twice. That's intentional here, not
wasteful: this script's local CSV is what compute_groundedness.py and
compute_semantic_similarity.py read from (no Supabase round-trip needed
for those), while run_pairwise_evaluation.py's job is specifically the
judge-vs-judge pairwise verdict, which needs live insert into
pairwise_evaluations for the existing feedback/analytics tooling that
already reads that table. Keeping them separate avoids reshaping a
script that's explicitly called out as "already exists, reused as-is."

Usage:
    python3 run_full_graph_generation.py [--start N] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.graph.graph_builder import build_graph  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parent.parent / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

PACING_SECONDS = 8  # Same Gemini free-tier reasoning as the pilot script.


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
    out_path = RESULTS_DIR / "clario_full_graph_drafts.csv"
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
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.start, args.limit))


if __name__ == "__main__":
    main()
