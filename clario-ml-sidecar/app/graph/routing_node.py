"""First-pass routing and the v3 one-time explicit reroute flip."""

from app.graph.state import TicketState

TECHNICAL_KEYWORDS = {
    "error": 2, "failed": 1, "crash": 3, "not working": 1, "bug": 2,
    # Authentication wording: the most common technical ticket the scorer used to miss.
    "login": 3, "log in": 3, "sign in": 3, "signin": 3, "password": 3,
    "locked out": 3, "authenticate": 3, "2fa": 3, "verification code": 2,
}
BILLING_KEYWORDS = {"payment": 3, "charged": 3, "bank": 2, "refund": 3, "billed": 3, "buying": 2, "billing": 3}

# "Account" qualifies both ways: account *access* is authentication (technical),
# account *billing* is billing. Match on the qualifier rather than the bare noun.
ACCOUNT_ACCESS_TERMS = ("access", "login", "log in", "sign in", "sign-in", "password", "auth", "credential", "locked")
ACCOUNT_BILLING_TERMS = ("billing", "payment", "invoice", "subscription", "refund", "charge")


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
    """Choose the initial specialist domain without modifying state. Routes to
    "both" (send to both specialists, not a guess) whenever the classifier
    itself is unsure or the ticket text carries a genuine dual-domain signal;
    "escalation" is reserved for when there's no usable signal at all."""
    # Low classifier confidence: don't trust the category, give both specialists a shot.
    if confidence is not None and confidence < 0.7:
        return "both"

    # No category at all: same reasoning as low confidence.
    if not category:
        return "both"

    tech_score = _calculate_score(text, TECHNICAL_KEYWORDS)
    billing_score = _calculate_score(text, BILLING_KEYWORDS)

    # The ticket text itself carries real signal for both domains (e.g. "payment
    # failed" - technical failure wording plus billing wording) - this overrides
    # a category label that may not reflect the whole ticket.
    if tech_score > 0 and billing_score > 0:
        return "both"

    # Primary logic: Trust the LLM's classification category
    cat_lower = category.lower()
    if "technical" in cat_lower or "tech" in cat_lower:
        return "technical"
    # Access wording wins over billing wording, so "Account Access" is not
    # swallowed by the billing branch on the bare word "account".
    if any(term in cat_lower for term in ACCOUNT_ACCESS_TERMS):
        return "technical"
    if any(term in cat_lower for term in ACCOUNT_BILLING_TERMS):
        return "billing"
    # A bare "Account" is genuinely ambiguous: fall through to scoring the
    # ticket text rather than guessing a domain from the label alone.

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
