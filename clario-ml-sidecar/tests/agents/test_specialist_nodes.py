"""Specialist node tests for context bookkeeping and failed-draft behavior."""

import asyncio

from app.agents.billing_agent.node import billing_agent_node
from app.agents.technical_agent.node import technical_agent_node


def test_technical_agent_records_none_and_low_relevance_on_draft_failure(monkeypatch) -> None:
    async def failing_generate(_: str) -> str:
        raise RuntimeError("unavailable")

    monkeypatch.setattr("app.agents.technical_agent.node.retrieve_context", lambda *_: [{
        "text": "Restart the app.", "source_file": "technical/app_crash.md", "score": 0.8
    }])
    monkeypatch.setattr("app.agents.technical_agent.node.generate", failing_generate)
    result = asyncio.run(technical_agent_node({"redacted_text": "The app crashed", "reflection_count": 0}))
    assert result["agent_drafts"]["technical"] is None
    assert result["low_relevance_flags"]["technical"] is True
    assert result["rag_top_score"]["technical"] == 0.8


def test_billing_agent_injects_prior_critique_and_records_draft(monkeypatch) -> None:
    seen: dict[str, str] = {}

    async def successful_generate(prompt: str) -> str:
        seen["prompt"] = prompt
        return "Review the pending authorization. [billing/payment_failed.md]"

    monkeypatch.setattr("app.agents.billing_agent.node.retrieve_context", lambda *_: [{
        "text": "A pending authorization can be released.", "source_file": "billing/payment_failed.md", "score": 0.9
    }])
    monkeypatch.setattr("app.agents.billing_agent.node.generate", successful_generate)
    result = asyncio.run(billing_agent_node({
        "redacted_text": "My payment failed", "reflection_count": 1,
        "reflection_critiques": ["Include the source."],
    }))
    assert "Your previous draft was rejected" in seen["prompt"]
    assert result["agent_drafts"]["billing"].startswith("Review")
    assert result["low_relevance_flags"]["billing"] is False
