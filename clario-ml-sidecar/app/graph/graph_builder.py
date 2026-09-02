"""v3 LangGraph wiring with bounded reroute and reflection loops."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from app.agents.billing_agent import billing_agent_node
from app.agents.technical_agent import technical_agent_node
from app.graph.cache_check_node import cache_check_node
from app.graph.classification_node import classification_node
from app.graph.escalation_node import escalation_node
from app.graph.handoff_node import handoff_node
from app.graph.surrogate_node import surrogate_node
from app.graph.analyzer_node import analyzer_node
from app.graph.resolve_node import resolve_node
from app.graph.reflection_node import reflection_node
from app.graph.response_judge_node import response_judge_node
from app.graph.routing_node import routing_node
from app.graph.state import TicketState
from app.graph.validation_node import validation_node

load_dotenv()



def _after_cache(state: TicketState) -> str:
    # If it's a cache hit, bypass validation (which requires context/redaction)
    # and go straight to response_judge (then escalation) to set the final_response
    return "response_judge" if state.get("cache_hit") else "surrogate"


def _specialist_target(state: TicketState) -> str:
    return {"technical": "technical_agent", "billing": "billing_agent", "escalation": "escalation"}[state["routing_decision"]]


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


def build_graph():
    """Compile the ticket graph; reroute and reflection are each structurally bounded."""
    graph = StateGraph(TicketState)
    graph.add_node("cache_check", cache_check_node)
    graph.add_node("surrogate", surrogate_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("classification", classification_node)
    graph.add_node("routing", routing_node)
    graph.add_node("technical_agent", technical_agent_node)
    graph.add_node("billing_agent", billing_agent_node)
    graph.add_node("validation", validation_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("response_judge", response_judge_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("handoff", handoff_node)
    graph.add_node("resolve", resolve_node)
    graph.add_edge(START, "cache_check")
    graph.add_conditional_edges("cache_check", _after_cache)
    graph.add_edge("surrogate", "analyzer")
    graph.add_edge("analyzer", "classification")
    graph.add_edge("classification", "routing")       # ← was missing; graph stopped here
    graph.add_conditional_edges("routing", _specialist_target)
    graph.add_edge("technical_agent", "validation")
    graph.add_edge("billing_agent", "validation")
    graph.add_conditional_edges("validation", _after_validation)
    graph.add_conditional_edges("reflection", _specialist_target)
    graph.add_edge("response_judge", "escalation")
    graph.add_edge("escalation", "resolve")
    graph.add_edge("resolve", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()
