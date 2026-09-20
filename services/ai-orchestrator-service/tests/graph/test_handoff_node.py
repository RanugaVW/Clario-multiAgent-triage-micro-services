"""Tests for the stable human-handoff package contract."""

from app.graph.handoff_node import build_handoff_package


def test_handoff_includes_dual_domain_diagnostics_and_reasoning() -> None:
    package = build_handoff_package({
        "ticket_id": "T-1", "redacted_text": "Payment failed", "category": "Billing",
        "priority": "High", "sentiment": "Negative", "classification_confidence": 0.8,
        "classification_source": "llama32_lora_v2", "routing_decision": "both",
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


def test_handoff_explains_the_critical_priority_escalation_trigger() -> None:
    # escalation_node emits "critical_priority"; the reviewer must get a real
    # sentence for it, not the generic "Escalation reason: <key>." fallback.
    package = build_handoff_package({
        "ticket_id": "T-2", "redacted_text": "Everything is down", "category": "Service Outage",
        "categories": ["Service Outage"], "priority": "Critical", "sentiment": "Frustrated",
        "escalation_triggered": True, "escalation_reasons": ["critical_priority"],
    })
    assert "critical" in package["reasoning_summary"].lower()
    assert "Escalation reason:" not in package["reasoning_summary"]


def test_handoff_classification_carries_every_category_label() -> None:
    package = build_handoff_package({
        "ticket_id": "T-3", "redacted_text": "Refund and the app crashes",
        "category": "Refunds, Technical Support", "categories": ["Refunds", "Technical Support"],
    })
    assert package["classification"]["category"] == "Refunds, Technical Support"
    assert package["classification"]["categories"] == ["Refunds", "Technical Support"]


def test_handoff_classification_categories_default_to_empty() -> None:
    assert build_handoff_package({"ticket_id": "T-4"})["classification"]["categories"] == []
