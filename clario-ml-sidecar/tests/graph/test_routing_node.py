"""Tests for initial routing and the v3 explicit reroute flip."""

from unittest.mock import patch

import pytest

from app.graph.routing_node import LOW_CATEGORY_CONFIDENCE, decide_routing, routing_node


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


def test_first_pass_routes_technical_billing_and_missing_category() -> None:
    assert routing_node(_state())["routing_decision"] == "technical"
    assert routing_node(_state(category="Billing", redacted_text="Need a refund"))["routing_decision"] == "billing"
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


def test_hr_hard_trigger_wins_even_against_stacked_billing_signal() -> None:
    # Real failure mode found by final review: "refund"+"payment" stacks to
    # billing_score=6, which always beat a single hr keyword (max weight 3)
    # under the old strict-maximum-over-all-three rule.
    result = routing_node(_state(
        category="Refund Request",
        redacted_text="My son enrolled without parental consent, please refund the payment.",
    ))
    assert result["routing_decision"] == "hr"


def test_hr_hard_trigger_instructor_change_wins_over_refund_wording() -> None:
    result = routing_node(_state(
        category="Refund Request",
        redacted_text="Wants a refund because the instructor was changed mid-course.",
    ))
    assert result["routing_decision"] == "hr"


def test_hr_weak_signal_sponsorship_does_not_misroute_a_routine_corporate_billing_ticket() -> None:
    # Regression check: "sponsorship" legitimately appears in ordinary
    # corporate-billing tickets in this repo's real dataset - must NOT be
    # promoted to a hard trigger, or this ticket would incorrectly route to HR.
    result = routing_node(_state(
        category="Refund Request",
        redacted_text="The course was paid for by his employer as a sponsorship, and any refund needs to go back to the company.",
    ))
    assert result["routing_decision"] == "billing"


def test_webxpay_alone_is_not_an_hr_signal() -> None:
    # webxpay is the payment gateway's own name - it appears throughout
    # ordinary billing tickets in this repo's real dataset and must not
    # trigger HR on its own.
    result = routing_node(_state(
        category="Billing Issue",
        redacted_text="WebXpay showed a payment failure message, but the amount was deducted from her bank account.",
    ))
    assert result["routing_decision"] == "billing"


# --- Llama-3.2 v2 taxonomy: multi-label categories -------------------------

@pytest.mark.parametrize(("category", "text", "expected"), [
    ("Billing & Invoicing", "Please explain this line on my statement.", "billing"),
    ("Refunds", "I would like my money back.", "billing"),
    ("Subscription Management", "Change my plan.", "billing"),
    ("Authentication", "Cannot get in.", "technical"),
    ("Account Access", "Cannot get in.", "technical"),
    # Categories the old substring rules never mapped to a domain.
    ("Performance", "Pages take ages to open.", "technical"),
    ("Data Integrity", "My grades look different.", "technical"),
    ("Service Outage", "Nothing loads for anyone.", "technical"),
    ("UI/UX", "The layout is confusing.", "technical"),
])
def test_taxonomy_categories_route_to_their_specialist_domain(category, text, expected) -> None:
    assert decide_routing(category, 0.95, text) == expected


def test_a_category_with_no_domain_falls_back_to_the_ticket_text() -> None:
    assert decide_routing("Feature Request", 0.95, "Could you add a dark mode?") == "escalation"
    assert decide_routing("Feature Request", 0.95, "I was charged twice, refund please") == "billing"


def test_a_ticket_spanning_both_domains_is_decided_by_the_ticket_text() -> None:
    category = "Refunds, Technical Support"
    assert decide_routing(category, 0.95, "I want a refund for this") == "billing"
    assert decide_routing(category, 0.95, "The page shows an error") == "technical"


def test_a_ticket_spanning_both_domains_with_no_text_signal_goes_to_both_specialists() -> None:
    assert decide_routing("Billing & Invoicing, Technical Support", 0.95, "Something is off with my account") == "both"


def test_categories_may_be_passed_as_a_list() -> None:
    assert decide_routing(["Authentication"], 0.95, "Cannot get in.") == "technical"


def test_free_text_categories_from_other_classifiers_still_route_as_before() -> None:
    assert decide_routing("Technical", 0.9, "hello there friend, how are you") == "technical"
    assert decide_routing("Billing", 0.9, "hello there friend, how are you") == "billing"
    assert decide_routing("Login Issue", 0.9, "hello there friend, how are you") == "technical"


# --- low classifier confidence: distrust the category, not the whole ticket ---

def test_low_confidence_ignores_the_category_and_routes_on_the_ticket_text() -> None:
    # The category says billing, but the classifier isn't sure; the text is clearly technical.
    assert decide_routing("Billing & Invoicing", 0.3, "The app crashed with an error") == "technical"


def test_low_confidence_with_no_text_signal_sends_the_ticket_to_both_specialists() -> None:
    assert decide_routing("Billing & Invoicing", 0.3, "Something is off with my account") == "both"


def test_low_confidence_does_not_bypass_the_hr_check() -> None:
    assert decide_routing("Billing & Invoicing", 0.1, "I had a medical emergency and cannot attend") == "hr"


def test_confidence_exactly_at_the_threshold_still_trusts_the_category() -> None:
    assert decide_routing("Refunds", LOW_CATEGORY_CONFIDENCE, "hello there friend, how are you") == "billing"
    assert decide_routing("Refunds", LOW_CATEGORY_CONFIDENCE - 0.01, "hello there friend, how are you") == "both"


def test_a_missing_confidence_is_treated_as_trusted() -> None:
    assert decide_routing("Refunds", None, "hello there friend, how are you") == "billing"


def test_routing_node_prefers_the_structured_category_list_over_the_joined_string() -> None:
    state = _state(category="General", categories=["Authentication"], redacted_text="Cannot get in.")
    assert routing_node(state)["routing_decision"] == "technical"
