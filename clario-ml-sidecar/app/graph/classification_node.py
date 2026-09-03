"""Graph node that records the temporary Gemini ticket classification."""

from app.graph.state import TicketState
from app.tools.classification_tool import classify_ticket


async def classification_node(state: TicketState) -> TicketState:
    """Classify redacted_text and write only classification-owned state fields."""
    result = await classify_ticket(state["redacted_text"])
    return {
        **state,
        "category": result["category"],
        "priority": result["priority"],
        "sentiment": result["sentiment"],
        "classification_confidence": result["confidence"],
        "classification_source": result["source"],
        # classify_ticket_local makes exactly one model call - no internal retry loop.
        "llm_call_count": state.get("llm_call_count", 0) + 1,
    }
