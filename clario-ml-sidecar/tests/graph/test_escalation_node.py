"""Independent branch coverage for the v3 escalation policy."""

import pytest

from app.graph.escalation_node import decide_escalation, escalation_node


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"priority": "Critical"}, "critical_priority"),
    ({"sentiment": "Negative"}, "negative_sentiment"),
    ({"routing_decision": "escalation"}, "no_usable_routing_signal"),
    ({"routing_decision": "both", "confidence": 0.5}, "low_confidence_dual_domain"),
    ({"failure_type": "dependency_failure"}, "dependency_failure"),
    ({"failure_type": "misroute", "routing_decision": "technical", "reroute_attempted": True}, "misroute_unresolved"),
    ({"failure_type": "quality", "reflection_count": 2}, "reflection_cap_reached"),
])
def test_each_escalation_branch(kwargs: dict, reason: str) -> None:
    values = {"priority": None, "sentiment": None, "routing_decision": "technical", "confidence": 0.9,
              "failure_type": "none", "reflection_count": 0, "max_reflection_attempts": 2,
              "reroute_attempted": False, "needs_reroute": False, **kwargs}
    escalated, reasons = decide_escalation(**values)
    assert escalated and reason in reasons


def test_both_domain_low_relevance_has_specific_reason() -> None:
    escalated, reasons = decide_escalation(None, None, "both", 0.9, "misroute", 0, 2, True, False)
    assert escalated and reasons == ["dual_domain_low_relevance"]


def test_node_writes_human_review_audit_fields() -> None:
    result = escalation_node({"priority": "Critical", "failure_type": "none"})
    assert result["escalation_triggered"] is True
    assert result["escalation_reasons"] == ["critical_priority"]
    assert "critical_priority" in result["human_review_notes"]


def test_node_escalates_a_ticket_routed_straight_to_escalation_with_no_draft() -> None:
    """Real bug, found live: routing_node's own "no usable signal" fallback
    (routing_decision="escalation") sends a ticket straight to this node,
    skipping every specialist agent - so agent_drafts is always {} here.
    Before the no_usable_routing_signal trigger existed, decide_escalation
    could find zero other reasons and report escalated=False, and this
    node would then try agent_drafts.get("escalation") -> None, leaving
    final_response None with escalated also False - main.py would then
    write status="resolved" with no draft and no resolution at all."""
    result = escalation_node({
        "priority": "Low", "sentiment": "Neutral", "routing_decision": "escalation",
        "failure_type": "none", "agent_drafts": {},
    })
    assert result["escalation_triggered"] is True
    assert result["escalation_reasons"] == ["no_usable_routing_signal"]
    assert result["final_response"] is None
