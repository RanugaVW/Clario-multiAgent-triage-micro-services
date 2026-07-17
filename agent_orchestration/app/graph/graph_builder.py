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
from app.graph.redaction_node import redaction_node
from app.graph.reflection_node import reflection_node
from app.graph.routing_node import routing_node
from app.graph.state import TicketState
from app.graph.validation_node import validation_node

load_dotenv()


async def both_specialists_node(state: TicketState) -> TicketState:
    """Run Technical and Billing specialists concurrently, then merge domain-keyed outputs."""
    technical, billing = await asyncio.gather(technical_agent_node(state), billing_agent_node(state))
    fields = ("agent_drafts", "retrieved_context", "rag_top_score", "low_relevance_flags")
    merged = {field: {**technical.get(field, {}), **billing.get(field, {})} for field in fields}
    return {**state, **merged}


def _after_cache(state: TicketState) -> str:
    return "validation" if state.get("cache_hit") else "redaction"


def _specialist_target(state: TicketState) -> str:
    return {"technical": "technical_agent", "billing": "billing_agent", "both": "both_specialists"}[state["routing_decision"]]


def _after_validation(state: TicketState) -> str:
    failure = state.get("failure_type")
    if failure == "dependency_failure":
        return "escalation"
    if failure == "misroute":
        return "routing" if state.get("needs_reroute") else "escalation"
    if failure in {"quality", "policy"}:
        limit = int(os.getenv("MAX_REFLECTION_ATTEMPTS", "2"))
        return "reflection" if state.get("reflection_count", 0) < limit else "escalation"
    return "escalation"


def build_graph():
    """Compile the ticket graph; reroute and reflection are each structurally bounded."""
    graph = StateGraph(TicketState)
    graph.add_node("cache_check", cache_check_node)
    graph.add_node("redaction", redaction_node)
    graph.add_node("classification", classification_node)
    graph.add_node("routing", routing_node)
    graph.add_node("technical_agent", technical_agent_node)
    graph.add_node("billing_agent", billing_agent_node)
    graph.add_node("both_specialists", both_specialists_node)
    graph.add_node("validation", validation_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("handoff", handoff_node)
    graph.add_edge(START, "cache_check")
    graph.add_conditional_edges("cache_check", _after_cache)
    graph.add_edge("redaction", "classification")
    graph.add_edge("classification", "routing")
    graph.add_conditional_edges("routing", _specialist_target)
    graph.add_edge("technical_agent", "validation")
    graph.add_edge("billing_agent", "validation")
    graph.add_edge("both_specialists", "validation")
    graph.add_conditional_edges("validation", _after_validation)
    graph.add_conditional_edges("reflection", _specialist_target)
    graph.add_edge("escalation", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()
