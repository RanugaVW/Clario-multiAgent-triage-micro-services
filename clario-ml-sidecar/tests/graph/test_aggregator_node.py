"""Aggregator agent: one merged reply for "both" tickets, safe fallback otherwise."""

import asyncio

from app.graph import aggregator_node as agg

TECH = "**[INTERNAL TECHNICAL REPORT]**\nGateway timeout.\n\n**[CUSTOMER RESPONSE]**\nHello, please wait ten minutes and try the payment again. [technical/app_crash.md]"
BILL = "**[INTERNAL TECHNICAL REPORT]**\nPending authorization.\n\n**[CUSTOMER RESPONSE]**\nHello, the pending hold is released by your bank within a few days. [billing/payment_failed.md]"
CONTEXT = {"technical": [{"text": "retry checkout", "score": 0.8}], "billing": [{"text": "hold released", "score": 0.8}]}


def _state(**overrides):
    return {"routing_decision": "both", "agent_drafts": {"technical": TECH, "billing": BILL},
            "retrieved_context": CONTEXT, "llm_call_count": 3, **overrides}


def test_merges_both_customer_replies_and_keeps_both_reports(monkeypatch):
    seen = {}
    def fake_llm(prompt, temperature):
        seen["prompt"] = prompt
        return ("Hello, please wait ten minutes and try the payment again [technical/app_crash.md]. "
                "The pending hold is released by your bank within a few days [billing/payment_failed.md].")
    monkeypatch.setattr(agg, "llm_invoke", fake_llm)
    result = asyncio.run(agg.aggregator_node(_state()))

    assert "try the payment again" in seen["prompt"] and "pending hold is released" in seen["prompt"]
    assert "Gateway timeout" not in seen["prompt"]  # internal reports never go to the merge
    merged = result["aggregated_response"]
    assert "Technical: Gateway timeout." in merged and "Billing: Pending authorization." in merged
    assert merged.split("**[CUSTOMER RESPONSE]**")[1].count("Hello") == 1
    assert result["aggregation"]["merged"] is True and result["llm_call_count"] == 4


def test_merge_that_breaks_a_policy_rule_falls_back_to_the_joined_drafts(monkeypatch):
    monkeypatch.setattr(agg, "llm_invoke", lambda p, t: "We guarantee a full refund today.")
    result = asyncio.run(agg.aggregator_node(_state()))
    assert result["aggregated_response"] == f"{TECH}\n\n{BILL}"
    assert result["aggregation"]["reason"] == "merged_reply_failed_policy"
    assert "unsupported_overcommitment" in result["aggregation"]["failed_rules"]


def test_merge_call_failure_falls_back(monkeypatch):
    def boom(*_):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(agg, "llm_invoke", boom)
    result = asyncio.run(agg.aggregator_node(_state()))
    assert result["aggregated_response"] == f"{TECH}\n\n{BILL}" and result["aggregation"]["merged"] is False


def test_single_domain_and_cache_hits_are_untouched(monkeypatch):
    def must_not_call(*_):
        raise AssertionError("no merge needed")
    monkeypatch.setattr(agg, "llm_invoke", must_not_call)
    for state in (_state(routing_decision="technical"), _state(cache_hit=True),
                  _state(agent_drafts={"technical": TECH, "billing": None})):
        assert "aggregated_response" not in asyncio.run(agg.aggregator_node(state))
