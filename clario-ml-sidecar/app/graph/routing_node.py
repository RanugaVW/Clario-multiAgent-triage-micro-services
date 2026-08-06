"""First-pass routing and the v3 one-time explicit reroute flip."""

from app.graph.state import TicketState

TECHNICAL_KEYWORDS = frozenset({"error", "failed", "crash", "not working", "bug"})
BILLING_KEYWORDS = frozenset({"payment", "charged", "bank", "refund", "billed"})


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    """Return whether a configured routing phrase occurs in text."""
    lower_text = text.lower()
    return any(keyword in lower_text for keyword in keywords)


def check_rag_required(text: str) -> bool:
    """Adaptive RAG: Bypass retrieval for very short or simple queries."""
    if len(text.split()) < 5:
        # Simple greetings or very short text often don't need RAG
        return False
    return True


def decide_routing(category: str | None, confidence: float | None, text: str) -> str:
    """Choose the initial specialist domain without modifying state. Routes to both if unsure."""
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
        text = state.get("redacted_text", "")
        decision = decide_routing(
            state.get("category"),
            state.get("classification_confidence"),
            text,
        )
        rag_required = check_rag_required(text)
        return {**state, "routing_decision": decision, "rag_required": rag_required}

    raise ValueError("Routing node received an invalid reroute state")
