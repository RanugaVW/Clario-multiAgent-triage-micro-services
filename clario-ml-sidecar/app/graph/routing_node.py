"""First-pass routing and the v3 one-time explicit reroute flip."""

from app.graph.state import TicketState

TECHNICAL_KEYWORDS = frozenset({"error", "failed", "crash", "not working", "bug"})
BILLING_KEYWORDS = frozenset({"payment", "charged", "bank", "refund", "billed"})


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    """Return whether a configured routing phrase occurs in text."""
    lower_text = text.lower()
    return any(keyword in lower_text for keyword in keywords)


def decide_routing(category: str | None, confidence: float | None, text: str) -> str:
    """Choose the initial specialist domain without modifying state."""
    if confidence is not None and confidence < 0.6:
        return "both"
    if _has_keyword(text, TECHNICAL_KEYWORDS) and _has_keyword(text, BILLING_KEYWORDS):
        return "both"
    if category == "Technical":
        return "technical"
    if category in {"Billing", "Account"}:
        return "billing"
    return "both"


def routing_node(state: TicketState) -> TicketState:
    """Route once, or flip technical/billing exactly once after a misroute."""
    needs_reroute = state.get("needs_reroute", False)
    reroute_attempted = state.get("reroute_attempted", False)
    current_decision = state.get("routing_decision")

    if needs_reroute and not reroute_attempted:
        if current_decision not in {"technical", "billing"}:
            raise ValueError("Cannot reroute a ticket without exactly one specialist domain")
        flipped = "billing" if current_decision == "technical" else "technical"
        return {**state, "routing_decision": flipped, "reroute_attempted": True}

    if not needs_reroute and not reroute_attempted:
        decision = decide_routing(
            state.get("category"),
            state.get("classification_confidence"),
            state.get("redacted_text", ""),
        )
        return {**state, "routing_decision": decision}

    raise ValueError("Routing node received an invalid reroute state")
