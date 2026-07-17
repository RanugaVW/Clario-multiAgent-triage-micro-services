"""Six mocked integration scenarios for the v3 graph's safety guarantees."""

import asyncio

from app.graph import graph_builder
from app.graph.escalation_node import escalation_node
from app.graph.handoff_node import handoff_node
from app.graph.reflection_node import reflection_node
from app.graph.routing_node import routing_node


def _install_stubs(monkeypatch, calls: dict[str, int]) -> None:
    def cache(state): return {**state, "cache_hit": False, "cache_source_ticket_id": None}
    def redact(state): return {**state, "redacted_text": state["raw_text"], "pii_found": []}
    async def classify(state):
        category = "Billing" if "clean billing" in state["raw_text"] else "Technical"
        return {**state, "category": category, "priority": "Medium", "sentiment": "Neutral", "classification_confidence": 0.9}
    def route(state):
        calls["routing"] += 1
        return routing_node(state)
    async def specialist(state, domain):
        return {**state, "agent_drafts": {**state.get("agent_drafts", {}), domain: "draft"},
                "retrieved_context": {**state.get("retrieved_context", {}), domain: [{"text": "context", "score": .9}]},
                "rag_top_score": {**state.get("rag_top_score", {}), domain: .9},
                "low_relevance_flags": {**state.get("low_relevance_flags", {}), domain: False}}
    async def technical(state): return await specialist(state, "technical")
    async def billing(state): return await specialist(state, "billing")
    async def validation(state):
        text = state["raw_text"]
        if "dual" in text:
            return {**state, "failure_type": "misroute", "needs_reroute": False, "reroute_attempted": True,
                    "low_relevance_flags": {"technical": True, "billing": True}, "validation_result": {}}
        if "reroute" in text and state["routing_decision"] == "technical":
            return {**state, "failure_type": "misroute", "needs_reroute": True, "validation_result": {}}
        if "quality" in text:
            return {**state, "failure_type": "quality", "needs_reroute": False,
                    "validation_result": {"technical": {"passed": False, "failed_rules": ["tone"], "reasoning": "revise"}}}
        return {**state, "failure_type": "none", "needs_reroute": False, "validation_result": {}}
    monkeypatch.setattr(graph_builder, "cache_check_node", cache); monkeypatch.setattr(graph_builder, "redaction_node", redact)
    monkeypatch.setattr(graph_builder, "classification_node", classify); monkeypatch.setattr(graph_builder, "routing_node", route)
    monkeypatch.setattr(graph_builder, "technical_agent_node", technical); monkeypatch.setattr(graph_builder, "billing_agent_node", billing)
    monkeypatch.setattr(graph_builder, "validation_node", validation); monkeypatch.setattr(graph_builder, "reflection_node", reflection_node)
    monkeypatch.setattr(graph_builder, "escalation_node", escalation_node); monkeypatch.setattr(graph_builder, "handoff_node", handoff_node)


def _run(monkeypatch, raw_text: str):
    calls = {"routing": 0}; _install_stubs(monkeypatch, calls)
    state = {"ticket_id": "T", "raw_text": raw_text, "reflection_count": 0, "reflection_critiques": [], "reroute_attempted": False, "needs_reroute": False}
    return asyncio.run(graph_builder.build_graph().ainvoke(state)), calls


def test_clean_technical(monkeypatch):
    result, _ = _run(monkeypatch, "clean technical error")
    assert result["routing_decision"] == "technical" and result["failure_type"] == "none" and not result["escalation_triggered"]


def test_clean_billing(monkeypatch):
    result, _ = _run(monkeypatch, "clean billing refund")
    assert result["routing_decision"] == "billing" and result["failure_type"] == "none" and not result["escalation_triggered"]


def test_ambiguous_payment_routes_both_initially(monkeypatch):
    result, calls = _run(monkeypatch, "Payment failed but the money was taken from my bank account")
    assert result["routing_decision"] == "both" and calls["routing"] == 1


def test_single_misroute_flips_once_and_passes(monkeypatch):
    result, _ = _run(monkeypatch, "reroute technical error")
    assert result["reroute_attempted"] and result["routing_decision"] == "billing" and result["failure_type"] == "none"


def test_dual_low_relevance_never_reinvokes_routing(monkeypatch):
    result, calls = _run(monkeypatch, "dual payment failed and bank charged")
    assert result["failure_type"] == "misroute" and not result["needs_reroute"]
    assert "dual_domain_low_relevance" in result["escalation_reasons"] and calls["routing"] == 1


def test_quality_reflects_exactly_twice_then_escalates(monkeypatch):
    result, _ = _run(monkeypatch, "quality technical error")
    assert result["reflection_count"] == 2 and "reflection_cap_reached" in result["escalation_reasons"]
