"""Failure-type branches for the v3 validation node."""

import asyncio

from app.graph.validation_node import validation_node


def _state(**overrides: object) -> dict:
    base = {"agent_drafts": {"technical": "Use the documented steps."}, "retrieved_context": {"technical": [{"text": "documented steps", "score": 0.9}]}, "rag_top_score": {"technical": 0.9}, "low_relevance_flags": {"technical": False}, "routing_decision": "technical", "reroute_attempted": False, "redacted_text": "Help", "pii_found": []}
    return {**base, **overrides}


def test_draft_failure_is_dependency_failure() -> None:
    result = asyncio.run(validation_node(_state(agent_drafts={"technical": None})))
    assert result["failure_type"] == "dependency_failure"


def test_both_low_relevance_escalates_without_reroute(monkeypatch) -> None:
    async def judge(*_: object) -> dict:
        return {"on_topic": False, "grounded_in_context": False, "appropriate_tone": True, "reasoning": "off-topic"}
    monkeypatch.setattr("app.graph.validation_node.llm_judge_check", judge)
    result = asyncio.run(validation_node(_state(agent_drafts={"technical": "x", "billing": "y"}, retrieved_context={"technical": [], "billing": []}, rag_top_score={"technical": 0.0, "billing": 0.0}, low_relevance_flags={"technical": True, "billing": True}, routing_decision="both")))
    assert result["failure_type"] == "misroute" and not result["needs_reroute"]
    assert result["reroute_attempted"] and result["dual_domain_low_confidence"]


def test_single_misroute_requests_exactly_one_flip(monkeypatch) -> None:
    async def judge(*_: object) -> dict:
        return {"on_topic": False, "grounded_in_context": True, "appropriate_tone": True, "reasoning": "wrong domain"}
    monkeypatch.setattr("app.graph.validation_node.llm_judge_check", judge)
    result = asyncio.run(validation_node(_state(rag_top_score={"technical": 0.0}, low_relevance_flags={"technical": True})))
    assert result["failure_type"] == "misroute" and result["needs_reroute"]


def test_already_rerouted_misroute_does_not_retry_again(monkeypatch) -> None:
    async def judge(*_: object) -> dict:
        return {"on_topic": False, "grounded_in_context": True, "appropriate_tone": True, "reasoning": "wrong domain"}
    monkeypatch.setattr("app.graph.validation_node.llm_judge_check", judge)
    result = asyncio.run(validation_node(_state(rag_top_score={"technical": 0.0}, low_relevance_flags={"technical": True}, reroute_attempted=True)))
    assert result["failure_type"] == "misroute" and not result["needs_reroute"]


def test_policy_and_quality_failures_are_distinguished(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_RANDOM_SAMPLE_RATE", "0")
    policy = asyncio.run(validation_node(_state(agent_drafts={"technical": ""})))
    assert policy["failure_type"] == "policy"
    async def judge(*_: object) -> dict:
        return {"on_topic": True, "grounded_in_context": False, "appropriate_tone": True, "reasoning": "ungrounded"}
    monkeypatch.setattr("app.graph.validation_node.llm_judge_check", judge)
    quality = asyncio.run(validation_node(_state(rag_top_score={"technical": 0.0})))
    assert quality["failure_type"] == "quality"
