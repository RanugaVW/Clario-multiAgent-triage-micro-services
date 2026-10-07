"""Specialist agents pick up learned agent-edit knowledge without disturbing retrieval gating."""

import asyncio

import pytest

from app.agents.billing_agent.node import billing_agent_node
from app.agents.hr_agent.node import _HR_EXTRA_INSTRUCTIONS, hr_agent_node
from app.agents.technical_agent.node import technical_agent_node

EDITS = [
    {"takeaway": "Refunds take 5-7 business days.", "edit_type": "factual", "similarity": 0.9, "review_id": "r1"},
    {"takeaway": "Open with an apology for the delay.", "edit_type": "style", "similarity": 0.8, "review_id": "r2"},
]
AGENTS = [
    ("technical", technical_agent_node, "app.agents.technical_agent.node"),
    ("billing", billing_agent_node, "app.agents.billing_agent.node"),
    ("hr", hr_agent_node, "app.agents.hr_agent.node"),
]


def _run(monkeypatch, module, node, edits, kb_score=0.4):
    seen = {}

    async def fake_generate(prompt):
        seen["prompt"] = prompt
        return "A draft.", 1

    monkeypatch.setattr(f"{module}.retrieve_context", lambda *_: [
        {"text": "KB text.", "source_file": "kb/a.md", "score": kb_score},
    ])
    monkeypatch.setattr(f"{module}.generate", fake_generate)
    monkeypatch.setattr(f"{module}.select_agent_edits", lambda *_a, **_k: edits)
    result = asyncio.run(node({"redacted_text": "I need a refund", "reflection_count": 0}))
    return result, seen["prompt"]


@pytest.mark.parametrize("domain,node,module", AGENTS)
def test_style_guidance_reaches_the_prompt_and_facts_join_the_context(monkeypatch, domain, node, module) -> None:
    result, prompt = _run(monkeypatch, module, node, EDITS)

    assert "Open with an apology for the delay." in prompt
    assert "Refunds take 5-7 business days." in prompt  # as a retrieved-context item
    context = result["retrieved_context"][domain]
    assert context[0]["source_file"] == "kb/a.md"
    assert context[-1] == {"source_file": "agent_edit_correction", "text": "Refunds take 5-7 business days.", "score": 0.0}


@pytest.mark.parametrize("domain,node,module", AGENTS)
def test_learned_facts_never_change_the_relevance_gate(monkeypatch, domain, node, module) -> None:
    result, _ = _run(monkeypatch, module, node, EDITS, kb_score=0.4)

    assert result["rag_top_score"][domain] == 0.4
    assert result["low_relevance_flags"][domain] is True  # weak KB match stays weak


@pytest.mark.parametrize("domain,node,module", AGENTS)
def test_no_edits_leaves_prompt_and_context_untouched(monkeypatch, domain, node, module) -> None:
    result, prompt = _run(monkeypatch, module, node, [])

    assert "Style guidance learned" not in prompt
    assert len(result["retrieved_context"][domain]) == 1


def test_hr_keeps_its_no_promises_instruction_alongside_the_guidance(monkeypatch) -> None:
    _, prompt = _run(monkeypatch, "app.agents.hr_agent.node", hr_agent_node, EDITS)

    assert _HR_EXTRA_INSTRUCTIONS in prompt
    assert "Open with an apology for the delay." in prompt
