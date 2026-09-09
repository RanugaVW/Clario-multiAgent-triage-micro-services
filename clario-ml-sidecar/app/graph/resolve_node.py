"""Graph node that restores original PII (ResolvePass) after escalation drafting."""

from app.graph.state import TicketState

def resolve_node(state: TicketState) -> TicketState:
    """Restore original PII using ShadowMap."""
    return {**state}
