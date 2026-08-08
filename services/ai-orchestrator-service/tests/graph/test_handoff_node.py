"""Tests for the stable human-handoff package contract."""

from app.graph.handoff_node import build_handoff_package


def test_handoff_includes_dual_domain_diagnostics_and_reasoning() -> None:
    package = build_handoff_package({
        "ticket_id": "T-1", "redacted_text": "Payment failed", "category": "Billing",
        "priority": "High", "sentiment": "Negative", "classification_confidence": 0.8,
        "classification_source": "gemini_stand_in", "routing_decision": "both",
        "agent_drafts": {"technical": None, "billing": "Review the transaction."},
        "retrieved_context": {"billing": [{"source_file": "billing/payment_failed.md", "score": 0.2}]},
        "rag_top_score": {"technical": 0.1, "billing": 0.2},
        "low_relevance_flags": {"technical": True, "billing": True},
        "validation_result": {"billing": {"judge_skipped": False, "judge_reason": "low_rag_score"}},
        "failure_type": "misroute", "escalation_triggered": True,
        "escalation_reasons": ["dual_domain_low_relevance"], "reflection_critiques": [],
        "cache_hit": True, "cache_source_ticket_id": "T-0",
    })
    assert package["specialists"]["technical"]["final_draft"] is None
    assert package["cache_source_ticket_id"] == "T-0"
    assert "Neither the Technical nor Billing" in package["reasoning_summary"]
    assert package["specialists"]["billing"]["validation"]["judge_reason"] == "low_rag_score"
