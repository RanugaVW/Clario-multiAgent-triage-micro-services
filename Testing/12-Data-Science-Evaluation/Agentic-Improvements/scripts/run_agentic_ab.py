"""Same-day A/B of the four agentic improvements on the 70 real LMS tickets.

Arms (run interleaved, ticket by ticket, so time-of-day API behaviour hits both):
  control - corrective RAG off, LLM supervisor off, judge gate off, aggregator
            off (old behaviour: drafts joined), no-progress stop off. Rule-driven
            reflection stays on, exactly as before.
  new     - all improvements on.

Both arms replay the SAME classifier labels the fine-tuned Llama gave each
ticket in the earlier full-graph run (Track C, *_after_gemini_distilled_llama.csv);
Llama decodes greedily, so these are the labels it produces. This isolates the
agentic changes from classifier variance and needs no GPU. The semantic cache
is forced to miss in both arms so every ticket reaches the specialists.

Usage (from the clario-ml-sidecar venv):
    python run_agentic_ab.py [--limit N]
Resumable: (arm, ticket) pairs already in results/ab_runs.jsonl are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EVAL = HERE.parents[1]
SIDECAR = EVAL.parents[1] / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR))
os.chdir(SIDECAR)  # .env and the relative CHROMA_PATH resolve from here

from app.graph import graph_builder as gb  # noqa: E402
from app.tools.taxonomy import split_category  # noqa: E402

OUT = HERE.parent / "results" / "ab_runs.jsonl"
TICKETS = EVAL / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
LABELS = EVAL / "Track-C-Response-Quality" / "results" / "clario_full_graph_drafts_after_gemini_distilled_llama.csv"
PACING_SECONDS = 3

ARM_ENV = {
    "control": {"CORRECTIVE_RAG_ENABLED": "false", "SUPERVISOR_LLM_ENABLED": "false",
                "JUDGE_REVISION_MIN_OVERALL": "0", "JUDGE_REVISION_MIN_DIMENSION": "0",
                "REFLECTION_NO_PROGRESS_STOP": "false"},
    "new": {"CORRECTIVE_RAG_ENABLED": "true", "SUPERVISOR_LLM_ENABLED": "true",
            "JUDGE_REVISION_MIN_OVERALL": "4", "JUDGE_REVISION_MIN_DIMENSION": "3",
            "REFLECTION_NO_PROGRESS_STOP": "true"},
}


def _labels() -> dict[str, dict]:
    d = pd.read_csv(LABELS).drop_duplicates("query_id").set_index("query_id")
    return {qid: {"category": r.category, "categories": split_category(r.category), "priority": r.priority,
                  "sentiment": r.sentiment, "classification_confidence": float(r.confidence)}
            for qid, r in d.iterrows()}


def build_arm_graph(arm: str, labels: dict[str, dict]):
    real_aggregator = gb.aggregator_node.__wrapped__ if hasattr(gb.aggregator_node, "__wrapped__") else gb.aggregator_node

    def cache_miss(state):
        return {**state, "cache_hit": False, "cache_source_ticket_id": None}

    async def replay_classification(state):
        return {**state, **labels[state["ticket_id"]], "classification_source": "llama32_lora_v2",
                "llm_call_count": state.get("llm_call_count", 0) + 1}

    async def no_aggregation(state):
        return {**state}

    gb.cache_check_node = cache_miss
    gb.classification_node = replay_classification
    gb.aggregator_node = real_aggregator if arm == "new" else no_aggregation
    return gb.build_graph()


def initial_state(qid: str, text: str) -> dict:
    return {"ticket_id": qid, "raw_text": text, "reflection_count": 0, "reflection_critiques": [],
            "reroute_attempted": False, "needs_reroute": False, "agent_drafts": {}, "retrieved_context": {},
            "rag_top_score": {}, "low_relevance_flags": {}, "validation_result": {}, "llm_call_count": 0}


def record(arm: str, qid: str, state: dict, seconds: float) -> dict:
    explanation = state.get("routing_explanation") or {}
    return {
        "arm": arm, "query_id": qid, "seconds": round(seconds, 1),
        "routing_decision": state.get("routing_decision"),
        "routing_rule": explanation.get("rule"),
        "supervisor": explanation.get("supervisor"),
        "escalation_triggered": state.get("escalation_triggered"),
        "escalation_reasons": state.get("escalation_reasons") or [],
        "drafts": state.get("agent_drafts") or {},
        "final_response": state.get("final_response"),
        "retrieved": {d: [{"source_file": c.get("source_file"), "score": c.get("score"), "text": c.get("text")} for c in ctx]
                      for d, ctx in (state.get("retrieved_context") or {}).items()},
        "corrective_rag": state.get("corrective_rag") or {},
        "judge": {d: {k: v for k, v in e.items() if k.endswith("_score") or k in
                      ("reasoning", "kept_pre_reflection_draft")}
                  for d, e in (state.get("judge_evaluations") or {}).items()},
        "reflection_count": state.get("reflection_count", 0),
        "reflection_sources": state.get("reflection_sources") or [],
        "aggregation": state.get("aggregation"),
        "llm_call_count": state.get("llm_call_count"),
        "validation_failures": state.get("failure_signature") or {},
        "redacted_text": state.get("redacted_text"),
        "priority": state.get("priority"),
        "category": state.get("category"),
    }


def done_pairs() -> set[tuple[str, str]]:
    if not OUT.exists():
        return set()
    with open(OUT, encoding="utf-8") as f:
        return {(r["arm"], r["query_id"]) for r in map(json.loads, f) if r.get("drafts") is not None}


async def main(limit: int | None) -> None:
    labels = _labels()
    tickets = pd.read_csv(TICKETS).to_dict("records")[:limit]
    done = done_pairs()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(tickets, 1):
        for arm in ("control", "new"):
            if (arm, t["query_id"]) in done:
                continue
            os.environ.update(ARM_ENV[arm])
            graph = build_arm_graph(arm, labels)
            start = time.time()
            try:
                state = await asyncio.wait_for(graph.ainvoke(initial_state(t["query_id"], t["query_text"])), 300)
                row = record(arm, t["query_id"], state, time.time() - start)
            except Exception as e:  # recorded, retried on the next run
                row = {"arm": arm, "query_id": t["query_id"], "error": repr(e)[:300], "drafts": None}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(tickets)}] {arm:7s} {t['query_id']} -> {row.get('routing_decision')} "
                  f"judge={ {d: j.get('overall_score') for d, j in (row.get('judge') or {}).items()} } "
                  f"rewrites={row.get('reflection_sources')} crag={list((row.get('corrective_rag') or {}).keys())} "
                  f"{row.get('error', '')}", flush=True)
            time.sleep(PACING_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    asyncio.run(main(parser.parse_args().limit))
