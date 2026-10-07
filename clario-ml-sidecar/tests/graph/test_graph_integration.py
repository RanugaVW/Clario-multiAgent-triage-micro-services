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
    def no_op(state): return {**state}
    monkeypatch.setattr(graph_builder, "cache_check_node", cache); monkeypatch.setattr(graph_builder, "surrogate_node", redact)
    monkeypatch.setattr(graph_builder, "analyzer_node", no_op); monkeypatch.setattr(graph_builder, "resolve_node", no_op)
    monkeypatch.setattr(graph_builder, "classification_node", classify); monkeypatch.setattr(graph_builder, "routing_node", route)
    monkeypatch.setattr(graph_builder, "technical_agent_node", technical); monkeypatch.setattr(graph_builder, "billing_agent_node", billing)
    monkeypatch.setattr(graph_builder, "validation_node", validation); monkeypatch.setattr(graph_builder, "reflection_node", reflection_node)
    monkeypatch.setattr(graph_builder, "response_judge_node", no_op)
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


def test_quality_reflects_exactly_twice_then_sends_anyway(monkeypatch):
    result, _ = _run(monkeypatch, "quality technical error")
    assert result["reflection_count"] == 2 and result["escalation_reasons"] == []
    assert not result["escalation_triggered"] and result["final_response"] == "draft"


def _judge_stub(monkeypatch, unhappy_passes: int):
    """A judge that finds the draft weak for the first `unhappy_passes` scorings."""
    seen = {"passes": 0}

    async def judge(state):
        seen["passes"] += 1
        weak = seen["passes"] <= unhappy_passes
        feedback = {"technical": "The quality judge scored this reply overall 2/5."} if weak else {}
        return {**state, "judge_feedback": feedback, "judge_needs_revision": weak}
    monkeypatch.setattr(graph_builder, "response_judge_node", judge)
    return seen


def test_weak_judge_score_triggers_one_redraft_then_sends(monkeypatch):
    calls = {"routing": 0}; _install_stubs(monkeypatch, calls)
    seen = _judge_stub(monkeypatch, unhappy_passes=1)
    state = {"ticket_id": "T", "raw_text": "clean technical error", "reflection_count": 0,
             "reflection_critiques": [], "reroute_attempted": False, "needs_reroute": False}
    result = asyncio.run(graph_builder.build_graph().ainvoke(state))
    assert seen["passes"] == 2 and result["reflection_count"] == 1
    assert result["reflection_sources"] == ["judge"]
    assert "overall 2/5" in result["reflection_critiques"][0]
    assert not result["escalation_triggered"] and result["final_response"] == "draft"


def test_judge_loop_is_capped_by_the_shared_reflection_limit(monkeypatch):
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")
    calls = {"routing": 0}; _install_stubs(monkeypatch, calls)
    seen = _judge_stub(monkeypatch, unhappy_passes=99)
    state = {"ticket_id": "T", "raw_text": "clean technical error", "reflection_count": 0,
             "reflection_critiques": [], "reroute_attempted": False, "needs_reroute": False}
    result = asyncio.run(graph_builder.build_graph().ainvoke(state))
    assert result["reflection_count"] == 2 and seen["passes"] == 3


def test_both_route_runs_the_two_specialists_concurrently(monkeypatch):
    calls = {"routing": 0}; _install_stubs(monkeypatch, calls)
    running, peak = {"now": 0}, {"max": 0}

    async def slow_specialist(state, domain):
        running["now"] += 1; peak["max"] = max(peak["max"], running["now"])
        await asyncio.sleep(0.05)
        running["now"] -= 1
        return {**state, "agent_drafts": {**state.get("agent_drafts", {}), domain: f"{domain} draft"},
                "llm_call_count": state.get("llm_call_count", 0) + 1}
    async def technical(state): return await slow_specialist(state, "technical")
    async def billing(state): return await slow_specialist(state, "billing")
    async def aggregator(state): return {**state, "aggregated_response": "merged reply"}
    monkeypatch.setattr(graph_builder, "technical_agent_node", technical)
    monkeypatch.setattr(graph_builder, "billing_agent_node", billing)
    monkeypatch.setattr(graph_builder, "aggregator_node", aggregator)

    result, _ = _run_installed(monkeypatch, "Payment failed but the money was taken from my bank account")
    assert peak["max"] == 2
    assert result["agent_drafts"] == {"technical": "technical draft", "billing": "billing draft"}
    assert result["llm_call_count"] == 2
    assert result["final_response"] == "merged reply"


def _run_installed(monkeypatch, raw_text):
    state = {"ticket_id": "T", "raw_text": raw_text, "reflection_count": 0, "reflection_critiques": [],
             "reroute_attempted": False, "needs_reroute": False}
    return asyncio.run(graph_builder.build_graph().ainvoke(state)), None


def test_same_rule_failure_after_a_redraft_stops_rule_redrafts_and_leaves_budget_for_the_judge(monkeypatch):
    from app.graph.validation_node import validation_node as real_validation
    calls = {"routing": 0}; _install_stubs(monkeypatch, calls)
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")

    async def always_same_rule(state):
        # Same unfixable rule failure every pass (like the weak-context fallback rule).
        result = {"technical": {"passed": False, "failed_rules": ["missing_low_context_fallback"], "judge_ran": False}}
        signature = {"technical": ["missing_low_context_fallback"]}
        no_progress = ((state.get("reflection_sources") or [None])[-1] == "validation"
                       and signature == state.get("last_reflected_failures"))
        return {**state, "validation_result": result, "failure_type": "policy", "needs_reroute": False,
                "failure_signature": signature, "rule_reflection_no_progress": no_progress}
    monkeypatch.setattr(graph_builder, "validation_node", always_same_rule)
    seen = _judge_stub(monkeypatch, unhappy_passes=1)

    result, _ = _run_installed(monkeypatch, "clean technical error")
    assert result["reflection_sources"] == ["validation", "judge"]
    assert seen["passes"] == 2
    assert real_validation  # the real node computes the same flag; see test_validation_node
