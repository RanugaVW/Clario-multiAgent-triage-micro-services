"""Stable, frontend-independent package for auto-send audit and human review."""

from app.graph.state import TicketState

_REASONING = {
    "urgent_priority": "This ticket is marked urgent and needs priority human handling.",
    "strongly_negative_sentiment": "The customer sentiment indicates a sensitive interaction requiring review.",
    "low_confidence_dual_domain": "Classification confidence was low and both specialist domains may be relevant.",
    "dependency_failure": "A required service was unavailable, so the response could not be verified safely.",
    "dual_domain_low_relevance": "Neither the Technical nor Billing knowledge base had strong matches for this ticket - needs human judgement on domain and resolution.",
    "misroute_unresolved": "The ticket was retried with the other specialist but remains off-topic or unsupported.",
    "reflection_cap_reached": "The draft did not pass validation after the allowed revision attempts.",
}


def build_handoff_package(state: TicketState) -> dict:
    """Build the /process_ticket handoff contract without side effects.

    JSON shape:
    {
      "ticket": {"ticket_id": str, "redacted_text": str},
      "classification": {"category": str|null, "priority": str|null,
        "sentiment": str|null, "confidence": number|null, "source": str|null},
      "routing_decision": str|null, "specialists_ran": [str],
      "specialists": {domain: {"final_draft": str|null, "retrieved_sources": [dict],
        "rag_top_score": number|null, "low_relevance": bool|null,
        "validation": dict|null}},
      "failure_type": str, "escalation": {"triggered": bool, "reasons": [str]},
      "reflection_critiques": [str], "cache_source_ticket_id": str|null,
      "reasoning_summary": str
    }
    """
    drafts = state.get("agent_drafts", {})
    specialists = {
        domain: {
            "final_draft": draft,
            "retrieved_sources": state.get("retrieved_context", {}).get(domain, []),
            "rag_top_score": state.get("rag_top_score", {}).get(domain),
            "low_relevance": state.get("low_relevance_flags", {}).get(domain),
            "validation": state.get("validation_result", {}).get(domain),
        }
        for domain, draft in drafts.items()
    }
    reasons = state.get("escalation_reasons", [])
    summary = " ".join(_REASONING.get(reason, f"Escalation reason: {reason}.") for reason in reasons)
    if not summary:
        summary = "Validation passed without requiring human escalation."
    return {
        "ticket": {"ticket_id": state.get("ticket_id"), "redacted_text": state.get("redacted_text")},
        "classification": {"category": state.get("category"), "priority": state.get("priority"),
                           "sentiment": state.get("sentiment"), "confidence": state.get("classification_confidence"),
                           "source": state.get("classification_source")},
        "routing_decision": state.get("routing_decision"), "specialists_ran": list(drafts),
        "specialists": specialists, "failure_type": state.get("failure_type", "none"),
        "escalation": {"triggered": state.get("escalation_triggered", False), "reasons": reasons},
        "reflection_critiques": state.get("reflection_critiques", []),
        "cache_source_ticket_id": state.get("cache_source_ticket_id") if state.get("cache_hit") else None,
        "reasoning_summary": summary,
    }


def handoff_node(state: TicketState) -> TicketState:
    """Terminal graph node; package construction remains explicit at the API boundary."""
    return state
