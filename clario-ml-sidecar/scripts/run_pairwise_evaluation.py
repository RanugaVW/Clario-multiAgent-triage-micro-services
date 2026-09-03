"""Compare generated drafts against real responses from an external
dataset (e.g. a Rysera LMS export), using the pairwise-preference judge.

For each row, drafts a response through the real LangGraph pipeline - the
same graph app/main.py uses, invoked directly rather than via
/process_ticket so replaying historical tickets never writes to the live
tickets/ticket_drafts/response_evaluations tables or the precedent cache
(see docs/superpowers/specs/2026-09-03-pairwise-judge-and-customer-
feedback-design.md §A.1) - then compares it against the real response.
Also captures the free absolute-rubric score the graph's own
response_judge_node already computes as a side effect.

Manual, one-off run. Run supabase_pairwise_feedback_schema.sql in the
Supabase SQL editor first.

    python clario-ml-sidecar/scripts/run_pairwise_evaluation.py --csv path/to/export.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from supabase import create_client  # noqa: E402

from app.graph.graph_builder import build_graph  # noqa: E402
from app.tools.redaction_tool import mask_pii  # noqa: E402
from app.tools.response_judge import get_judge  # noqa: E402

logger = logging.getLogger(__name__)


def _build_initial_state(ticket_id: str, raw_text: str) -> dict:
    """Mirror app/main.py's process_ticket initial_state exactly, so the
    graph runs the same way it would for a real incoming ticket."""
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


def _get_supabase():
    url = os.environ.get("SUPABASE_PROJECT_URL", "")
    key = os.environ.get("SUPABASE_SECRET_API", "")
    return create_client(url, key)


async def _evaluate_one_ticket(
    graph, judge, supabase, eval_run_id: str, row: dict, args, results: list | None = None
) -> bool:
    """Returns True if at least one domain's draft was evaluated and
    inserted into pairwise_evaluations, False if the row was skipped
    entirely (no draft produced, every domain's draft was empty, or the
    ticket was served from the precedent cache).

    If `results` is given, one dict mirroring each inserted row's
    category/final_winner/absolute_overall_score is appended to it, so
    callers can aggregate a summary without drifting from what was
    actually stored.
    """
    source_doc_id = row["_source_doc_id"]
    raw_text = row[args.ticket_col]
    reference_raw = row[args.response_col]
    source_url = row.get(args.source_col)

    initial_state = _build_initial_state(source_doc_id, raw_text)
    final_state = await graph.ainvoke(initial_state)

    if final_state.get("cache_hit"):
        logger.warning(f"{source_doc_id}: cache hit, skipping (eval measures fresh generation, not cache reuse)")
        return False

    agent_drafts = final_state.get("agent_drafts") or {}
    if not agent_drafts:
        logger.warning(f"{source_doc_id}: no draft produced, skipping")
        return False

    reference_redacted, _ = mask_pii(reference_raw)
    ticket_text = final_state.get("redacted_text") or raw_text
    category = final_state.get("category") or "Unknown"
    priority = final_state.get("priority") or "Medium"
    judge_evaluations = final_state.get("judge_evaluations") or {}

    inserted_any = False
    for domain, draft in agent_drafts.items():
        if not draft:
            logger.warning(f"{source_doc_id}: empty draft for domain={domain}, skipping")
            continue

        verdict = await judge.compare_draft_to_reference(
            ticket_issue=ticket_text,
            priority=priority,
            category=category,
            draft=draft,
            reference=reference_redacted,
        )

        absolute_score = (judge_evaluations.get(domain) or {}).get("overall_score")

        payload = {
            "eval_run_id": eval_run_id,
            "source_doc_id": source_doc_id,
            "category": category,
            "domain": domain,
            "priority": priority,
            "source_url": source_url,
            "ticket_text": ticket_text,
            "generated_draft": draft,
            "reference_response": reference_redacted,
            "winner_pass1": verdict.winner_pass1,
            "winner_pass2": verdict.winner_pass2,
            "reasoning_pass1": verdict.reasoning_pass1,
            "reasoning_pass2": verdict.reasoning_pass2,
            "final_winner": verdict.final_winner,
            "absolute_overall_score": absolute_score,
            "judge_model": verdict.judge_model,
            "evaluation_latency_ms": verdict.evaluation_latency_ms,
        }
        supabase.table("pairwise_evaluations").insert(payload).execute()
        inserted_any = True

        if results is not None:
            results.append({
                "category": payload["category"],
                "final_winner": payload["final_winner"],
                "absolute_overall_score": payload["absolute_overall_score"],
            })

    return inserted_any


def _summarize(rows: list[dict]) -> dict:
    """Aggregate inserted pairwise_evaluations rows into win/lose/tie counts
    (overall and per category) plus mean absolute_overall_score per category.

    Mirrors the exact fields inserted into pairwise_evaluations, so the
    printed summary can never drift from what was actually stored.
    """
    overall_counts: dict[str, int] = {}
    per_category_counts: dict[str, dict[str, int]] = {}
    per_category_scores: dict[str, list[float]] = {}

    for row in rows:
        winner = row.get("final_winner")
        category = row.get("category") or "Unknown"

        overall_counts[winner] = overall_counts.get(winner, 0) + 1

        cat_counts = per_category_counts.setdefault(category, {})
        cat_counts[winner] = cat_counts.get(winner, 0) + 1

        score = row.get("absolute_overall_score")
        if score is not None:
            per_category_scores.setdefault(category, []).append(score)

    per_category_mean_score: dict[str, float | str] = {}
    for category in per_category_counts:
        scores = per_category_scores.get(category) or []
        per_category_mean_score[category] = (sum(scores) / len(scores)) if scores else "no score data"

    return {
        "overall_counts": overall_counts,
        "per_category_counts": per_category_counts,
        "per_category_mean_score": per_category_mean_score,
    }


async def run(args) -> dict:
    graph = build_graph()
    judge = get_judge()
    supabase = _get_supabase()
    eval_run_id = datetime.now(timezone.utc).isoformat()

    summary = {"processed": 0, "skipped": 0, "failed": 0}
    results: list[dict] = []

    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row["_source_doc_id"] = f"rysera_row_{i}"
            try:
                processed = await _evaluate_one_ticket(graph, judge, supabase, eval_run_id, row, args, results)
                if processed:
                    summary["processed"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as e:
                logger.error(f"Row {i} failed: {e}")
                summary["failed"] += 1

    logger.info(f"Pairwise evaluation run {eval_run_id}: {summary}")

    stats = _summarize(results)
    logger.info(f"Overall win/lose/tie counts: {stats['overall_counts']}")
    logger.info(f"Per-category win/lose/tie counts: {stats['per_category_counts']}")
    logger.info(f"Per-category mean absolute_overall_score: {stats['per_category_mean_score']}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=str, help="Path to the external export CSV")
    parser.add_argument("--ticket-col", default="ticket_text")
    parser.add_argument("--source-col", default="source")
    parser.add_argument("--response-col", default="response")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
