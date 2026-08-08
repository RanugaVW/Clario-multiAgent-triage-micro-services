"""Graph node that performs Semantic Distillation before routing."""

from app.graph.state import TicketState

def analyzer_node(state: TicketState) -> TicketState:
    """Extract location, symptom, and capability features."""
    return {**state}
