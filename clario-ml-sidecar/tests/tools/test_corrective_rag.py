"""Corrective RAG: one query rewrite + re-search when the first search is weak."""

import asyncio

from app.agents.billing_agent.node import billing_agent_node
from app.tools.rag_tool import correct_retrieval

WEAK = [{"text": "weak", "source_file": "billing/currency.md", "score": 0.55}]
STRONG = [{"text": "strong", "source_file": "billing/refund_status.md", "score": 0.82}]


def test_strong_first_search_is_left_alone():
    def must_not_be_called(*_):
        raise AssertionError("no rewrite or retry expected")
    context, record, calls = correct_retrieval("where is my refund", "billing", STRONG,
                                               must_not_be_called, must_not_be_called)
    assert context is STRONG and record is None and calls == 0


def test_weak_search_is_rewritten_and_the_stronger_result_kept():
    seen = []
    def retrieve(query, domain):
        seen.append(query)
        return STRONG
    context, record, calls = correct_retrieval("money not back??", "billing", WEAK, retrieve,
                                               lambda q, d: "refund status pending bank")
    assert context is STRONG and calls == 1 and seen == ["refund status pending bank"]
    assert record == {"rewritten_query": "refund status pending bank", "score_before": 0.55,
                      "score_after": 0.82, "used_rewrite": True}


def test_a_worse_retry_keeps_the_original_context():
    worse = [{"text": "x", "source_file": "billing/tax_charge.md", "score": 0.40}]
    context, record, _ = correct_retrieval("q", "billing", WEAK, lambda *_: worse, lambda q, d: "other q")
    assert context is WEAK and record["used_rewrite"] is False and record["score_after"] == 0.4


def test_a_failed_rewrite_does_not_search_again():
    def must_not_be_called(*_):
        raise AssertionError("retry with the same query is pointless")
    context, record, _ = correct_retrieval("same", "billing", WEAK, must_not_be_called, lambda q, d: q)
    assert context is WEAK and record["used_rewrite"] is False


def test_a_reflection_redraft_reuses_the_earlier_rewrite_without_a_new_llm_call():
    def must_not_be_called(*_):
        raise AssertionError("rewrite should be reused")
    _, record, calls = correct_retrieval("q", "billing", WEAK, lambda *_: STRONG, must_not_be_called,
                                         prior={"rewritten_query": "cached rewrite"})
    assert calls == 0 and record["rewritten_query"] == "cached rewrite"


def test_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("CORRECTIVE_RAG_ENABLED", "false")
    context, record, calls = correct_retrieval("q", "billing", WEAK, None, None)
    assert context is WEAK and record is None and calls == 0


def test_billing_agent_drafts_from_the_corrected_context_and_counts_the_call(monkeypatch):
    seen = {}

    async def generate(prompt):
        seen["prompt"] = prompt
        return "Refunds take a few business days. [billing/refund_status.md]", 1

    monkeypatch.setattr("app.agents.billing_agent.node.retrieve_context",
                        lambda query, domain: STRONG if query == "refund status" else WEAK)
    monkeypatch.setattr("app.agents.billing_agent.node.rewrite_query", lambda q, d: "refund status")
    monkeypatch.setattr("app.agents.billing_agent.node.generate", generate)
    result = asyncio.run(billing_agent_node({"redacted_text": "money not back??", "reflection_count": 0}))

    assert "billing/refund_status.md" in seen["prompt"]
    assert result["rag_top_score"]["billing"] == 0.82
    assert result["corrective_rag"]["billing"]["used_rewrite"] is True
    assert result["llm_call_count"] == 2  # rewrite + draft
