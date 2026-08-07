"""First-pass routing and the v3 one-time explicit reroute flip."""

from app.graph.state import TicketState

TECHNICAL_KEYWORDS = {"error": 2, "failed": 1, "crash": 3, "not working": 1, "bug": 2}
BILLING_KEYWORDS = {"payment": 3, "charged": 3, "bank": 2, "refund": 3, "billed": 3, "buying": 2, "billing": 3}


def _calculate_score(text: str, weighted_keywords: dict[str, int]) -> int:
    """Calculate a domain score based on keyword weights."""
    lower_text = text.lower()
    score = 0
    for keyword, weight in weighted_keywords.items():
        if keyword in lower_text:
            score += weight
    return score


def check_rag_required(text: str) -> bool:
    """Adaptive RAG: Bypass retrieval for very short or simple queries."""
    if len(text.split()) < 5:
        # Simple greetings or very short text often don't need RAG
        return False
    return True


def decide_routing(category: str | None, confidence: float | None, text: str) -> str:
    """Choose the initial specialist domain without modifying state. Routes to escalation if unsure."""
    if confidence is not None and confidence < 0.7:
        return "escalation"
        
    # Primary logic: Trust the LLM's classification category
    if category == "Technical":
        return "technical"
    if category in {"Billing", "Account"}:
        return "billing"
        
    # Fallback logic: Compute weighted scores if category is missing or unrecognized
    tech_score = _calculate_score(text, TECHNICAL_KEYWORDS)
    billing_score = _calculate_score(text, BILLING_KEYWORDS)
    
    if tech_score > 0 or billing_score > 0:
        if billing_score > tech_score:
            return "billing"
        if tech_score > billing_score:
            return "technical"
        # If scores are exactly tied and > 0, we can't decide confidently
        return "escalation"
        
    return "escalation"


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
