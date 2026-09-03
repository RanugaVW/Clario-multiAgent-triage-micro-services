"""Graph node that redacts inbound ticket content before downstream processing."""

from app.graph.state import TicketState
from app.tools.redaction_tool import mask_pii_reversible


def surrogate_node(state: TicketState) -> TicketState:
    """Write redacted_text, pii_found, and pii_shadow_map while preserving raw_text unchanged."""
    redacted_text, shadow_map, pii_found = mask_pii_reversible(state["raw_text"])
    return {
        **state,
        "redacted_text": redacted_text,
        "pii_found": pii_found,
        "pii_shadow_map": shadow_map,
    }
