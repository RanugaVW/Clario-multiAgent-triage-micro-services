"""Typed shared state carried through the ticket-orchestration graph."""

from typing import Literal, TypedDict

# Shared blackboard - do not write to a field you don't own; see docstrings.
# failure_type is the single source of truth the graph_builder uses to decide
# between reroute / reflection / escalation - see graph_builder.py's conditional edges.


class TicketState(TypedDict):
    """State for redaction -> classification -> routing -> drafting -> validation."""

    # Input/API writes; every node reads to identify the ticket.
    ticket_id: str
    # Input/API writes; redaction_node alone reads raw customer content.
    raw_text: str
    # redaction_node writes; all downstream text-processing nodes read this only.
    redacted_text: str
    # redaction_node writes; validation_node reads for outgoing PII checks.
    pii_found: list[dict]
    # classification_node writes; routing_node, escalation_node, and handoff_node read.
    category: str | None
    # classification_node writes; escalation_node and handoff_node read.
    priority: str | None
    # classification_node writes; escalation_node and handoff_node read.
    sentiment: str | None
    # classification_node writes; routing_node, escalation_node, and handoff_node read.
    classification_confidence: float | None
    # classification_node writes; handoff_node reads the model/fallback provenance.
    classification_source: Literal["gemini_stand_in", "gemini_stand_in_fallback", "fine_tuned_model"]
    # routing_node writes; specialist, validation, escalation, and handoff nodes read.
    routing_decision: Literal["technical", "billing", "both"] | None
    # specialist nodes write; validation, reflection, escalation, and handoff nodes read.
    agent_drafts: dict[str, str | None]
    # specialist nodes write; validation, reflection, and handoff nodes read.
    retrieved_context: dict[str, list[dict]]
    # specialist nodes write; validation and handoff nodes read.
    rag_top_score: dict[str, float]
    # specialist nodes write; validation, escalation, and handoff nodes read.
    low_relevance_flags: dict[str, bool]
    # validation_node writes; escalation_node and handoff_node read dual-domain failures.
    dual_domain_low_confidence: bool
    # validation_node writes; escalation_node and handoff_node read.
    validation_result: dict[str, dict]
    # validation_node writes; graph_builder and escalation_node read for next-step routing.
    failure_type: Literal["misroute", "quality", "policy", "dependency_failure", "none"]
    # validation_node writes; routing_node and graph_builder read for the reroute edge.
    needs_reroute: bool
    # routing_node writes; validation_node, graph_builder, and escalation_node read.
    reroute_attempted: bool
    # reflection_node writes; specialist, graph_builder, escalation, and handoff nodes read.
    reflection_count: int
    # reflection_node writes; specialist nodes and handoff_node read.
    reflection_critiques: list[str]
    # cache_check_node writes; graph_builder and handoff_node read.
    cache_hit: bool
    # cache_check_node writes; handoff_node reads for cache provenance.
    cache_source_ticket_id: str | None
    # escalation_node writes; handoff_node and API response handling read.
    escalation_triggered: bool
    # escalation_node writes; handoff_node reads to explain the outcome.
    escalation_reasons: list[str]
    # escalation_node writes for auto-send; handoff_node and API response handling read.
    final_response: str | None
    # escalation_node writes for human review; handoff_node reads.
    human_review_notes: str | None
