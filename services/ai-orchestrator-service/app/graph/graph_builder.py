"""v3 LangGraph wiring with bounded reroute and reflection loops."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from app.agents.billing_agent import billing_agent_node
from app.agents.hr_agent import hr_agent_node
from app.agents.technical_agent import technical_agent_node
from app.graph.aggregator_node import aggregator_node
from app.graph.cache_check_node import cache_check_node
from app.graph.classification_node import classification_node
from app.graph.escalation_node import escalation_node
from app.graph.handoff_node import handoff_node
from app.graph.supervisor_node import supervisor_node
from app.graph.surrogate_node import surrogate_node
from app.graph.analyzer_node import analyzer_node
from app.graph.resolve_node import resolve_node
from app.graph.reflection_node import reflection_node
from app.graph.response_judge_node import response_judge_node
from app.graph.routing_node import routing_node
from app.graph.state import TicketState
from app.graph.validation_node import validation_node
from app.tracing.pipeline_tracer import trace_node

load_dotenv()



def _after_cache(state: TicketState) -> str:
    # If it's a cache hit, bypass validation (which requires context/redaction)
    # and go straight to response_judge (then escalation) to set the final_response
    return "response_judge" if state.get("cache_hit") else "surrogate"


def _specialist_target(state: TicketState) -> str:
    return {
        "technical": "technical_agent", "billing": "billing_agent",
        "both": "both_specialists", "escalation": "escalation", "hr": "hr_agent",
    }[state["routing_decision"]]


_PER_DOMAIN_KEYS = ("agent_drafts", "retrieved_context", "rag_top_score", "low_relevance_flags", "corrective_rag")


def _merge_specialist_results(state: TicketState, results: dict[str, TicketState]) -> TicketState:
    """Fold each specialist's own-domain entries back into one state."""
    merged = dict(state)
    for key in _PER_DOMAIN_KEYS:
        merged[key] = {**state.get(key, {})}
        for domain, result in results.items():
            if domain in result.get(key, {}):
                merged[key][domain] = result[key][domain]
    base = state.get("llm_call_count", 0)
    merged["llm_call_count"] = base + sum(r.get("llm_call_count", base) - base for r in results.values())
    if any(r.get("failure_type") == "dependency_failure" for r in results.values()):
        merged["failure_type"] = "dependency_failure"
    return merged


async def _both_specialists_node(state: TicketState) -> TicketState:
    """Draft both domains for an ambiguous ticket, in parallel.

    The two specialists run concurrently inside this one node (asyncio.gather)
    rather than as a LangGraph fan-out: every node returns `{**state, ...}`, and
    two branches writing the same keys in one step hit LangGraph's
    InvalidUpdateError unless every key had a reducer. Each specialist gets the
    same input state and only its own domain's entries are merged back.
    """
    technical, billing = await asyncio.gather(technical_agent_node(state), billing_agent_node(state))
    return _merge_specialist_results(state, {"technical": technical, "billing": billing})


def _after_validation(state: TicketState) -> str:
    """Route after validation based on failure_type signal."""
    failure = state.get("failure_type", "none")
    if failure == "dependency_failure":
        return "response_judge"
    if failure == "misroute":
        return "routing" if state.get("needs_reroute") else "response_judge"
    if failure in {"quality", "policy"}:
        limit = int(os.getenv("MAX_REFLECTION_ATTEMPTS", "2"))
        return "reflection" if state.get("reflection_count", 0) < limit else "response_judge"
    # failure_type == "none": validation passed → go to response_judge, then escalation node
    # escalation_node checks priority/sentiment to decide auto-resolve vs human review
    return "response_judge"


def _after_judge(state: TicketState) -> str:
    """Evaluator-optimizer gate: a weak judge score gets one more bounded redraft.

    Shares MAX_REFLECTION_ATTEMPTS with rule-driven reflection, so the total
    number of redrafts per ticket never grows. Cache hits have no specialist to
    redraft; misroute/dependency failures are not fixable by rewording.
    """
    limit = int(os.getenv("MAX_REFLECTION_ATTEMPTS", "2"))
    if (state.get("judge_needs_revision") and not state.get("cache_hit")
            and state.get("failure_type", "none") not in {"misroute", "dependency_failure"}
            and state.get("reflection_count", 0) < limit):
        return "reflection"
    return "aggregator"


def build_graph():
    """Compile the ticket graph; reroute and reflection are each structurally bounded."""
    graph = StateGraph(TicketState)
    graph.add_node("cache_check", trace_node("cache_check")(cache_check_node))
    graph.add_node("surrogate", trace_node("surrogate")(surrogate_node))
    graph.add_node("analyzer", trace_node("analyzer")(analyzer_node))
    graph.add_node("classification", trace_node("classification")(classification_node))
    graph.add_node("routing", trace_node("routing")(routing_node))
    graph.add_node("supervisor", trace_node("supervisor")(supervisor_node))
    graph.add_node("technical_agent", trace_node("technical_agent")(technical_agent_node))
    graph.add_node("billing_agent", trace_node("billing_agent")(billing_agent_node))
    graph.add_node("both_specialists", trace_node("both_specialists")(_both_specialists_node))
    graph.add_node("hr_agent", trace_node("hr_agent")(hr_agent_node))
    graph.add_node("validation", trace_node("validation")(validation_node))
    graph.add_node("reflection", trace_node("reflection")(reflection_node))
    graph.add_node("response_judge", trace_node("response_judge")(response_judge_node))
    graph.add_node("aggregator", trace_node("aggregator")(aggregator_node))
    graph.add_node("escalation", trace_node("escalation")(escalation_node))
    graph.add_node("handoff", trace_node("handoff")(handoff_node))
    graph.add_node("resolve", trace_node("resolve")(resolve_node))
    graph.add_edge(START, "cache_check")
    graph.add_conditional_edges("cache_check", _after_cache)
    graph.add_edge("surrogate", "analyzer")
    graph.add_edge("analyzer", "classification")
    graph.add_edge("classification", "routing")       # ← was missing; graph stopped here
    graph.add_edge("routing", "supervisor")
    graph.add_conditional_edges("supervisor", _specialist_target)
    graph.add_edge("technical_agent", "validation")
    graph.add_edge("billing_agent", "validation")
    graph.add_edge("both_specialists", "validation")
    graph.add_edge("hr_agent", "validation")
    graph.add_conditional_edges("validation", _after_validation)
    graph.add_conditional_edges("reflection", _specialist_target)
    graph.add_conditional_edges("response_judge", _after_judge)
    graph.add_edge("aggregator", "escalation")
    graph.add_edge("escalation", "resolve")
    graph.add_edge("resolve", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()
