"""hr_agent mirrors technical_agent/billing_agent's node shape exactly -
same retrieve/circuit-breaker/generate flow, domain="hr"."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.hr_agent.node import hr_agent_node
from app.tools.circuit_breaker import CircuitBreakerOpenError


def _state(**overrides: object) -> dict:
    state = {
        "redacted_text": "My bank slip was rejected but nobody explained why.",
        "agent_drafts": {}, "retrieved_context": {}, "rag_top_score": {},
        "low_relevance_flags": {}, "failure_type": "none", "llm_call_count": 0,
        "reflection_count": 0,
    }
    return {**state, **overrides}


@pytest.mark.asyncio
async def test_hr_agent_writes_a_grounded_draft() -> None:
    context = [{"source_file": "hr/payment_linkage_escalation.md", "text": "...", "score": 0.8}]
    with patch("app.agents.hr_agent.node.retrieve_context", return_value=context), \
         patch("app.agents.hr_agent.node.check_relevance", return_value=True), \
         patch("app.agents.hr_agent.node.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = ("A reviewer will look into this.", 1)
        result = await hr_agent_node(_state())

    assert result["agent_drafts"]["hr"] == "A reviewer will look into this."
    assert result["retrieved_context"]["hr"] == context
    assert result["rag_top_score"]["hr"] == 0.8
    assert result["low_relevance_flags"]["hr"] is False
    assert result["failure_type"] == "none"
    assert result["llm_call_count"] == 1


@pytest.mark.asyncio
async def test_hr_agent_reports_dependency_failure_on_circuit_breaker_open() -> None:
    with patch("app.agents.hr_agent.node.retrieve_context", side_effect=CircuitBreakerOpenError("open")):
        result = await hr_agent_node(_state())

    assert result["agent_drafts"]["hr"] is None
    assert result["failure_type"] == "dependency_failure"
    assert result["low_relevance_flags"]["hr"] is True


@pytest.mark.asyncio
async def test_hr_agent_prompt_avoids_overpromising() -> None:
    """The one real difference from technical_agent/billing_agent: hr_agent's
    prompt must tell the model not to promise outcomes it can't guarantee."""
    context = [{"source_file": "hr/course_cancellation.md", "text": "...", "score": 0.7}]
    with patch("app.agents.hr_agent.node.retrieve_context", return_value=context), \
         patch("app.agents.hr_agent.node.check_relevance", return_value=True), \
         patch("app.agents.hr_agent.node.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = ("draft", 1)
        await hr_agent_node(_state())

    prompt_used = mock_generate.call_args.args[0]
    assert "do not promise" in prompt_used.lower()
