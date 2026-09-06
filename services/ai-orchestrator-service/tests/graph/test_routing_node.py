"""Tests for initial routing and the v3 explicit reroute flip."""

from unittest.mock import patch

import pytest

from app.graph.routing_node import decide_routing, routing_node


def _state(**overrides: object) -> dict:
    state = {
        "category": "Technical",
        "classification_confidence": 0.9,
        "redacted_text": "The app has an error.",
        "routing_decision": None,
        "needs_reroute": False,
        "reroute_attempted": False,
    }
    return {**state, **overrides}


def test_first_pass_routes_technical_billing_low_confidence_and_missing_category() -> None:
    assert routing_node(_state())["routing_decision"] == "technical"
    assert routing_node(_state(category="Billing", redacted_text="Need a refund"))["routing_decision"] == "billing"
    assert routing_node(_state(classification_confidence=0.5))["routing_decision"] == "both"
    assert routing_node(_state(category=None, classification_confidence=0.9))["routing_decision"] == "both"


def test_ambiguous_payment_failure_routes_to_both_on_first_pass() -> None:
    result = routing_node(_state(
        redacted_text="Payment failed but the money was taken from my bank account"
    ))
    assert result["routing_decision"] == "both"


def test_reroute_flips_domain_without_rederiving_routing() -> None:
    with patch("app.graph.routing_node.decide_routing", wraps=decide_routing) as decision_spy:
        result = routing_node(_state(
            routing_decision="technical", needs_reroute=True, reroute_attempted=False
        ))
    assert result["routing_decision"] == "billing"
    assert result["reroute_attempted"] is True
    decision_spy.assert_not_called()


def test_reroute_of_both_is_rejected_defensively() -> None:
    with pytest.raises(ValueError, match="Cannot reroute"):
        routing_node(_state(routing_decision="both", needs_reroute=True))


def test_hr_signal_wins_over_lexically_overlapping_billing_score() -> None:
    # "bank slip" scores billing_score > 0 via the existing "bank" keyword,
    # and hr_score > 0 via "bank slip" itself - hr must win, not "both" or "billing".
    result = routing_node(_state(
        category="Billing Issue",
        redacted_text="My bank slip was rejected but nobody explained why.",
    ))
    assert result["routing_decision"] == "hr"


def test_hr_does_not_win_when_it_is_not_the_strict_maximum() -> None:
    # "locked out" (technical, weight 3) outscores "misclassified" (hr, weight 2) -
    # hr must not win here; falls through to existing category/keyword logic.
    result = routing_node(_state(
        category="Technical",
        redacted_text="I was locked out and I think my account got misclassified.",
    ))
    assert result["routing_decision"] == "technical"


def test_hr_never_combines_with_both() -> None:
    # Pure tech+billing dual-signal, no hr keywords at all - unaffected by the new check.
    result = routing_node(_state(
        redacted_text="Payment failed but the money was taken from my bank account"
    ))
    assert result["routing_decision"] == "both"
