"""Escalation policy and auditable v3 human-review reason strings."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.graph.state import TicketState

load_dotenv()


def decide_escalation(
    priority: str | None,
    sentiment: str | None,
    routing_decision: str | None,
    confidence: float | None,
    failure_type: str,
    reflection_count: int,
    max_reflection_attempts: int,
    reroute_attempted: bool,
    needs_reroute: bool = False,
) -> tuple[bool, list[str]]:
    """Return whether review is mandatory and every specific reason that applies."""
    reasons: list[str] = []
    if priority == "Urgent":
        reasons.append("urgent_priority")
    if sentiment == "Strongly Negative":
        reasons.append("strongly_negative_sentiment")
    if routing_decision == "both" and confidence is not None and confidence < 0.6:
        reasons.append("low_confidence_dual_domain")
    if failure_type == "dependency_failure":
        reasons.append("dependency_failure")
    if failure_type == "misroute" and reroute_attempted and not needs_reroute:
        reasons.append("dual_domain_low_relevance" if routing_decision == "both" else "misroute_unresolved")
    if failure_type in {"quality", "policy"} and reflection_count >= max_reflection_attempts:
        reasons.append("reflection_cap_reached")
    return bool(reasons), reasons


def escalation_node(state: TicketState) -> TicketState:
    """Write escalation outcome after validation or reflection has reached a terminal path."""
    escalated, reasons = decide_escalation(
        state.get("priority"), state.get("sentiment"), state.get("routing_decision"),
        state.get("classification_confidence"), state.get("failure_type", "none"),
        state.get("reflection_count", 0), int(os.getenv("MAX_REFLECTION_ATTEMPTS", "2")),
        state.get("reroute_attempted", False), state.get("needs_reroute", False),
    )
    notes = "Human review required: " + ", ".join(reasons) if escalated else None
    drafts = state.get("agent_drafts", {})
    if state.get("routing_decision") == "both":
        response = "\n\n".join(draft for draft in drafts.values() if draft)
    else:
        response = drafts.get(state.get("routing_decision"))
    return {**state, "escalation_triggered": escalated, "escalation_reasons": reasons,
            "human_review_notes": notes, "final_response": None if escalated else response}
