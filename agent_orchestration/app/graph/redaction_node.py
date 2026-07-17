"""Graph node that redacts inbound ticket content before downstream processing."""

from app.graph.state import TicketState
from app.tools.redaction_tool import mask_pii


def redaction_node(state: TicketState) -> TicketState:
    """Write redacted_text and pii_found while preserving raw_text unchanged."""
    redacted_text, pii_found = mask_pii(state["raw_text"])
    return {**state, "redacted_text": redacted_text, "pii_found": pii_found}
