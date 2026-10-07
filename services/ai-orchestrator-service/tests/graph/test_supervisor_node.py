"""Hybrid supervisor: LLM routing only where the rules are unsure."""

import asyncio

from app.graph import supervisor_node as sup
from app.graph.routing_node import routing_node


def _routed(text, categories, confidence):
    return routing_node({"redacted_text": text, "categories": categories, "category": ", ".join(categories),
                         "classification_confidence": confidence, "needs_reroute": False,
                         "reroute_attempted": False, "llm_call_count": 1})


def test_clear_tickets_keep_the_rule_decision_without_an_llm_call(monkeypatch):
    def must_not_call(*_):
        raise AssertionError("rules were confident")
    monkeypatch.setattr(sup, "llm_invoke", must_not_call)
    state = _routed("I was charged twice for my course", ["Billing & Invoicing"], 0.95)
    result = asyncio.run(sup.supervisor_node(state))
    assert result["routing_decision"] == "billing" and result["llm_call_count"] == 1
    assert "supervisor" not in result["routing_explanation"]


def test_uncertain_ticket_is_decided_by_the_supervisor(monkeypatch):
    seen = {}
    def fake_llm(prompt, temperature):
        seen["prompt"] = prompt
        return '{"domain": "billing", "reason": "The customer asks to change their learning plan."}'
    monkeypatch.setattr(sup, "llm_invoke", fake_llm)
    state = _routed("Can I move to the cheaper plan next month?", ["Feature Request"], 0.9)
    assert state["routing_explanation"]["rule"] == "no_signal" and state["routing_decision"] == "escalation"

    result = asyncio.run(sup.supervisor_node(state))
    assert result["routing_decision"] == "billing"
    assert result["routing_explanation"]["decision"] == "billing"
    assert result["routing_explanation"]["supervisor"] == {
        "used": True, "rule_decision": "escalation", "decision": "billing",
        "reason": "The customer asks to change their learning plan."}
    assert result["llm_call_count"] == 2
    assert "<user_ticket>\nCan I move to the cheaper plan next month?\n</user_ticket>" in seen["prompt"]
    assert "refund eligibility" in seen["prompt"]  # KB topics are listed


def test_bad_or_failed_answers_keep_the_rule_decision(monkeypatch):
    state = _routed("Can I move to the cheaper plan next month?", ["Feature Request"], 0.9)
    for answer in ('{"domain": "marketing", "reason": "x"}', "not json", '{"domain": "billing"}'):
        monkeypatch.setattr(sup, "llm_invoke", lambda p, t, a=answer: a)
        result = asyncio.run(sup.supervisor_node(state))
        assert result["routing_decision"] == "escalation"
        assert result["routing_explanation"]["supervisor"]["used"] is False

    def boom(*_):
        raise RuntimeError("no key")
    monkeypatch.setattr(sup, "llm_invoke", boom)
    assert asyncio.run(sup.supervisor_node(state))["routing_decision"] == "escalation"


def test_reroute_pass_and_disabled_flag_skip_the_supervisor(monkeypatch):
    def must_not_call(*_):
        raise AssertionError("must not run")
    monkeypatch.setattr(sup, "llm_invoke", must_not_call)
    state = _routed("Can I move to the cheaper plan next month?", ["Feature Request"], 0.9)
    asyncio.run(sup.supervisor_node({**state, "reroute_attempted": True}))
    monkeypatch.setenv("SUPERVISOR_LLM_ENABLED", "false")
    assert asyncio.run(sup.supervisor_node(state))["routing_decision"] == "escalation"
