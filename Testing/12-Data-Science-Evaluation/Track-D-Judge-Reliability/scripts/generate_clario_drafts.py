"""Track D, step 1: generate Clario's real drafts + ResponseJudge scores for
the 70-ticket set, so Track D has something to sample from.

Deliberately bypasses classification_node and routing_node - confirmed by a
smoke test that the real local classifier + keyword router escalates most
of these 70 tickets before any specialist ever runs (a real Track B
finding, not a bug), which would leave nothing for Track D to sample from.
Track D's own question - does ResponseJudge's score of a drafted reply
match what a human would give it - only needs a real draft to exist; it
doesn't need the routing decision that got it there to be realistic. So
this script calls the correct specialist node(s) directly, using Track A's
already-verified ground-truth domain(s) for each ticket (same decoupling
principle Track A itself used: it called retrieve_context() directly with
the ground-truth domain, bypassing routing_node too). This is a separate,
clearly-labeled file - it cannot be confused with whatever Track B/C
produce from the real routing path.

Still real and unmodified: PII redaction (surrogate_node), retrieval
(retrieve_context), the specialist's own LLM draft generation, few-shot
selection, and ResponseJudge's scoring - only classification+routing are
skipped. A ground-truth row naming more than one domain (e.g. "billing,hr")
runs each named specialist in turn, exactly like graph_builder.py's
_both_specialists_node composes technical_agent_node + billing_agent_node.

Usage:
    python3 generate_clario_drafts.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.agents.billing_agent.node import billing_agent_node  # noqa: E402
from app.agents.hr_agent.node import hr_agent_node  # noqa: E402
from app.agents.technical_agent.node import technical_agent_node  # noqa: E402
from app.graph.surrogate_node import surrogate_node  # noqa: E402
from app.tools.few_shot_selector import select_few_shots  # noqa: E402
from app.tools.response_judge import evaluate_draft  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parents[1] / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

SPECIALIST_NODES = {
    "technical": technical_agent_node,
    "billing": billing_agent_node,
    "hr": hr_agent_node,
}
DEFAULT_PRIORITY = "Medium"
DEFAULT_CATEGORY = "Unknown"

# The Gemini free tier caps generate_content at 15 requests/minute PER MODEL,
# and draft generation + judging currently share one model (GEMINI_DRAFT_MODEL
# and GEMINI_JUDGE_MODEL both resolve to gemini-3.1-flash-lite in .env) - so
# each domain-draft costs 2 calls against the SAME 15/minute budget. A first,
# unpaced run confirmed this the hard way: it blew through the quota by
# ticket ~20 and every retry immediately re-hit the same limit (no backoff
# room left), producing only 16 usable rows out of 70. 8s between each
# domain-draft, on top of the pair's own inference latency, keeps sustained
# usage comfortably under 15/minute with room for an occasional retry.
PACING_SECONDS = 8


def load_ground_truth() -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_base_state(ticket_id: str, raw_text: str) -> dict:
    """Minimal real state a specialist node needs, mirroring the fields
    app/main.py's process_ticket initializes - reflection/rerouting fields
    included even though this script never triggers those paths, since the
    specialist nodes read reflection_count/reflection_critiques unconditionally."""
    return {
        "ticket_id": ticket_id,
        "raw_text": raw_text,
        "priority": DEFAULT_PRIORITY,
        "category": DEFAULT_CATEGORY,
        "reflection_count": 0,
        "reflection_critiques": [],
        "agent_drafts": {},
        "retrieved_context": {},
        "rag_top_score": {},
        "low_relevance_flags": {},
    }


async def draft_and_judge_one_domain(state: dict, domain: str) -> dict | None:
    """Runs one specialist node, then judges its draft exactly the way
    response_judge_node does. Returns None if no draft was produced."""
    node = SPECIALIST_NODES[domain]
    state = await node(state)
    draft = (state.get("agent_drafts") or {}).get(domain)
    if not draft:
        return None

    ticket_issue = state["redacted_text"]
    priority = state["priority"]
    category = state["category"]
    retrieved = (state.get("retrieved_context") or {}).get(domain, [])

    try:
        few_shots = await select_few_shots(ticket_issue, priority, domain if domain in ("technical", "billing") else "technical")
    except Exception as e:
        print(f"    few-shot selection failed for domain={domain}: {e}")
        few_shots = []

    score = await evaluate_draft(draft, priority, category, ticket_issue, few_shots, retrieved)
    top_sources = ";".join(m.get("source_file", "") for m in retrieved)
    return {
        "draft": draft,
        "retrieved_sources": top_sources,
        "judge_overall_score": score.overall_score,
        "judge_priority_tone_match_score": score.priority_tone_match_score,
        "judge_completeness_score": score.completeness_score,
        "judge_accuracy_score": score.accuracy_score,
        "judge_policy_compliance_score": score.policy_compliance_score,
        "judge_groundedness_score": score.groundedness_score,
        "judge_reasoning": score.reasoning,
        "judge_model": score.judge_model,
    }


async def run(limit: int | None) -> None:
    rows = load_ground_truth()
    if limit:
        rows = rows[:limit]

    out_rows: list[dict] = []
    skipped_no_draft = 0
    failed = 0

    for i, row in enumerate(rows, start=1):
        qid = row["query_id"]
        domains = [d.strip() for d in row["domain"].split(",") if d.strip()]
        print(f"[{i}/{len(rows)}] {qid} (domains={domains}): {row['query_text'][:55]!r}", flush=True)

        base_state = build_base_state(qid, row["query_text"])
        try:
            base_state = surrogate_node(base_state)
        except Exception as e:
            print(f"  FAILED (surrogate): {e}")
            failed += 1
            continue

        for domain in domains:
            try:
                result = await draft_and_judge_one_domain(dict(base_state), domain)
            except Exception as e:
                print(f"  FAILED domain={domain}: {e}")
                failed += 1
                await asyncio.sleep(PACING_SECONDS)
                continue
            if result is None:
                print(f"  domain={domain}: no draft produced")
                skipped_no_draft += 1
                await asyncio.sleep(PACING_SECONDS)
                continue
            print(f"  domain={domain}: judge_overall={result['judge_overall_score']}")
            out_rows.append({
                "query_id": qid,
                "gt_domain": row["domain"],
                "domain_drafted": domain,
                "priority": base_state["priority"],
                "category": base_state["category"],
                **result,
            })
            await asyncio.sleep(PACING_SECONDS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "clario_drafts_and_judge_scores.csv"
    if out_rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)

    summary = {
        "tickets_processed": len(rows),
        "draft_rows_written": len(out_rows),
        "skipped_no_draft": skipped_no_draft,
        "failed": failed,
    }
    print(json.dumps(summary, indent=2))
    with open(RESULTS_DIR / "generation_run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {len(out_rows)} rows to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N tickets (for a smoke test)")
    args = parser.parse_args()
    asyncio.run(run(args.limit))


if __name__ == "__main__":
    main()
