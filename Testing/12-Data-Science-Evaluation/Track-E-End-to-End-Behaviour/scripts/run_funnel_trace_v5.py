"""Track E, step 3 (v5) - full 70-ticket verification of BOTH real fixes
together, at proper sample size (v4 only targeted the 15 tickets already
known to reflect, cheaply, to check the critique fix before committing to
this larger run):

1. response_judge_node.py / reflection_node.py (verified in v3, n=15): keeps
   whichever of the pre-reflection or rewritten draft actually scores higher,
   instead of always accepting the rewrite.
2. validation_node.py's llm_judge_check (verified in v4, n=13): names the
   specific failed check in its critique instead of the constant, useless
   string "local_heuristic_judge".

This script re-scores each reflected ticket's pre-reflection snapshot with
the same judge used on the final draft (same wrapper technique as v2/v3/v4),
across all 70 tickets rather than a targeted subset, to get a properly
powered answer on whether fix 2 actually moves the needle.

Usage:
    python3 run_funnel_trace_v5.py [--start N] [--limit N]
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

import app.graph.graph_builder as gb  # noqa: E402
from app.tools.few_shot_selector import select_few_shots  # noqa: E402
from app.tools.response_judge import evaluate_draft  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parent.parent / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

PACING_SECONDS = 8

# ticket_id -> {domain: {"draft": str, "retrieved_context": list[dict]}} - first call only
_pre_reflection: dict[str, dict[str, dict]] = {}
_seen: set[tuple[str, str]] = set()


def _wrap_specialist(original_fn):
    async def wrapped(state):
        result = await original_fn(state)
        ticket_id = state.get("ticket_id")
        drafts = result.get("agent_drafts") or {}
        context = result.get("retrieved_context") or {}
        for domain, draft in drafts.items():
            key = (ticket_id, domain)
            if draft and key not in _seen:
                _seen.add(key)
                _pre_reflection.setdefault(ticket_id, {})[domain] = {
                    "draft": draft,
                    "retrieved_context": context.get(domain, []),
                }
        return result
    return wrapped


# Patch the names graph_builder itself calls (module-level lookup, so this
# takes effect for every path that reaches these nodes, including
# _both_specialists_node's direct calls).
gb.technical_agent_node = _wrap_specialist(gb.technical_agent_node)
gb.billing_agent_node = _wrap_specialist(gb.billing_agent_node)
gb.hr_agent_node = _wrap_specialist(gb.hr_agent_node)


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


async def _score_pre_reflection(ticket_id: str, final_state: dict) -> dict:
    """Re-score each domain's first draft with the same judge used on the final
    draft, so reflected tickets get a genuine before/after pair. Only called
    for tickets where reflection actually ran."""
    snapshot = _pre_reflection.get(ticket_id, {})
    if not snapshot:
        return {}
    priority = final_state.get("priority") or "Medium"
    category = final_state.get("category") or "Unknown"
    ticket_issue = final_state.get("redacted_text") or final_state.get("raw_text", "")
    scores = {}
    for domain, snap in snapshot.items():
        judge_domain = domain if domain in ("technical", "billing") else "technical"
        try:
            few_shots = await select_few_shots(ticket_issue, priority, judge_domain)
        except Exception:
            few_shots = []
        try:
            score = await evaluate_draft(
                snap["draft"], priority, category, ticket_issue, few_shots, snap["retrieved_context"],
            )
            scores[domain] = score.overall_score
        except Exception as e:
            print(f"  pre-reflection scoring failed for {ticket_id}/{domain}: {e}", flush=True)
    return scores


async def run(start: int, limit: int | None) -> None:
    graph = gb.build_graph()
    rows = load_queries()
    rows = rows[start:start + limit] if limit else rows[start:]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "funnel_trace_v5.csv"
    fieldnames = [
        "query_id", "gt_domain", "routing_decision", "classification_confidence",
        "cache_hit", "reflection_count", "failure_type", "needs_reroute", "reroute_attempted",
        "escalation_triggered", "escalation_reasons", "wall_clock_seconds",
        "pre_reflection_judge_score_mean", "final_judge_score_mean", "error",
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
                    "wall_clock_seconds": f"{elapsed:.2f}", "pre_reflection_judge_score_mean": "",
                    "final_judge_score_mean": "", "error": str(e)[:200],
                })
                failed += 1
                f.flush()
                _pre_reflection.pop(qid, None)
                time.sleep(PACING_SECONDS)
                continue

            reflection_count = final_state.get("reflection_count", 0)
            pre_scores, final_scores = {}, {}
            if reflection_count > 0:
                pre_scores = await _score_pre_reflection(qid, final_state)
                for domain, ev in (final_state.get("judge_evaluations") or {}).items():
                    if ev.get("overall_score") is not None:
                        final_scores[domain] = ev["overall_score"]

            pre_mean = sum(pre_scores.values()) / len(pre_scores) if pre_scores else ""
            final_mean = sum(final_scores.values()) / len(final_scores) if final_scores else ""

            writer.writerow({
                "query_id": qid,
                "gt_domain": gt_domain,
                "routing_decision": final_state.get("routing_decision"),
                "classification_confidence": final_state.get("classification_confidence"),
                "cache_hit": final_state.get("cache_hit", False),
                "reflection_count": reflection_count,
                "failure_type": final_state.get("failure_type", "none"),
                "needs_reroute": final_state.get("needs_reroute", False),
                "reroute_attempted": final_state.get("reroute_attempted", False),
                "escalation_triggered": final_state.get("escalation_triggered", False),
                "escalation_reasons": ";".join(final_state.get("escalation_reasons") or []),
                "wall_clock_seconds": f"{elapsed:.2f}",
                "pre_reflection_judge_score_mean": pre_mean,
                "final_judge_score_mean": final_mean,
                "error": "",
            })
            processed += 1
            f.flush()
            _pre_reflection.pop(qid, None)
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
