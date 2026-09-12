"""Track D PILOT, step 1: generate Clario's real drafts + ResponseJudge
scores for the 99-query baseline set (Track A's original, broader dataset -
built partly from real tickets, partly hand-written), run as a calibration
pass BEFORE trusting the "official" 70-real-ticket run.

Why run this first: the 70-ticket run already found and fixed two real
judge problems (the rigid required-phrase rubric, then API rate-limiting -
see ../README.md). The 99-query set is a different, larger, more varied
sample (62 billing / 27 technical / 10 HR vs. the 70-set's more even split,
and includes hand-written edge cases Track A's own report notes score
differently from real tickets) - exactly the kind of second, independent
dataset that surfaces gaps a single dataset's fixes might have missed,
before spending human-annotation effort calibrating against the "real"
one. Same principle Track A itself used: every KB/threshold change in
TEST_REPORT_V2.md was checked against both the 70-ticket set AND this same
99-query set, specifically to avoid conclusions that only held on one.

Same bypass-classification-and-routing approach as the sibling script
(../../scripts/generate_clario_drafts.py) and the same reasoning applies:
Track D only needs a real draft to exist, not a realistic routing path.
The one structural difference: this ground truth has exactly one domain
per row (no unions), and "HR" is capitalized here where the real-ticket
ground truth uses lowercase "hr" - normalized below before dispatch, since
retrieve_context() requires the exact lowercase string.

Usage:
    python3 generate_clario_drafts_99.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[5] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.agents.billing_agent.node import billing_agent_node  # noqa: E402
from app.agents.hr_agent.node import hr_agent_node  # noqa: E402
from app.agents.technical_agent.node import technical_agent_node  # noqa: E402
from app.graph.surrogate_node import surrogate_node  # noqa: E402
from app.tools.few_shot_selector import select_few_shots  # noqa: E402
from app.tools.response_judge import evaluate_draft  # noqa: E402

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parents[2] / "Track-A-Retrieval-Quality" / "data" / "retrieval_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"

SPECIALIST_NODES = {
    "technical": technical_agent_node,
    "billing": billing_agent_node,
    "hr": hr_agent_node,
}
DEFAULT_PRIORITY = "Medium"
DEFAULT_CATEGORY = "Unknown"

# Same shared-quota constraint as the sibling script: draft generation and
# judging both call gemini-3.1-flash-lite, capped at 15 requests/minute on
# the free tier. 8s between domain-drafts keeps sustained usage safely
# under that shared budget - see ../../scripts/generate_clario_drafts.py's
# docstring for the failure this was learned from.
PACING_SECONDS = 8


def load_ground_truth(limit: int | None) -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["domain"] = row["domain"].strip().lower()
    if limit:
        rows = rows[:limit]
    return rows


def build_base_state(ticket_id: str, raw_text: str) -> dict:
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
    rows = load_ground_truth(limit)

    out_rows: list[dict] = []
    skipped_no_draft = 0
    failed = 0

    for i, row in enumerate(rows, start=1):
        qid = row["query_id"]
        domain = row["domain"]
        print(f"[{i}/{len(rows)}] {qid} (domain={domain}): {row['query_text'][:55]!r}", flush=True)

        if domain not in SPECIALIST_NODES:
            print(f"  SKIPPED: unrecognized domain {domain!r}")
            skipped_no_draft += 1
            continue

        base_state = build_base_state(qid, row["query_text"])
        try:
            base_state = surrogate_node(base_state)
        except Exception as e:
            print(f"  FAILED (surrogate): {e}")
            failed += 1
            continue

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
    out_path = RESULTS_DIR / "clario_drafts_and_judge_scores_99.csv"
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
    with open(RESULTS_DIR / "generation_run_summary_99.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {len(out_rows)} rows to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N queries (for a smoke test)")
    args = parser.parse_args()
    asyncio.run(run(args.limit))


if __name__ == "__main__":
    main()
