"""Semantic-cache boundary; currently a deliberate no-op until caching is enabled."""

from app.graph.state import TicketState


def cache_check_node(state: TicketState) -> TicketState:
    """Declare a cache miss while preserving the graph contract for future cache support."""
    return {**state, "cache_hit": False, "cache_source_ticket_id": None}
