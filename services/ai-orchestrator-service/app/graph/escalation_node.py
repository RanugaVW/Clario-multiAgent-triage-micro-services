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
    # The local classifier (Llama-3.2 adapter, see app/tools/local_llm.py)
    # was empirically confirmed to top out at "Critical" priority - it does
    # not produce "Urgent" (a previous, differently-trained adapter's tier).
    if priority == "Critical":
        reasons.append("critical_priority")
    # `sentiment` is intentionally not a trigger here (it was, until Track
    # B's 99-query pilot measured it against 71 human-labeled tickets:
    # "Negative" sentiment showed no real correlation with actual escalation
    # need - if anything inversely, since 24 of 36 High-priority+Negative
    # tickets should NOT escalate - because an ordinary "my payment failed"
    # complaint reads as negative sentiment even with a documented KB
    # answer). Removing it as a standalone trigger measured precision
    # 0.439->0.741 and F1 0.588->0.727 for a recall cost of 0.893->0.714, a
    # net win; the triggers below already cover genuine severity.
    # routing_node's own fallback for "no usable technical/billing signal at
    # all" (see decide_routing's final `return "escalation"`) sends the
    # ticket straight to this node, skipping every specialist agent - so
    # agent_drafts is always empty here. Without this check, decide_escalation
    # could find zero *other* triggers (priority/sentiment/confidence all
    # unremarkable) and report escalated=False - which left main.py with no
    # draft and no final_response, yet still wrote status="resolved"
    # unconditionally, showing the customer an empty "Resolved" ticket with
    # nothing in it. Found live via the admin console on a real ticket.
    if routing_decision == "escalation":
        reasons.append("no_usable_routing_signal")
    if routing_decision == "hr":
        reasons.append("hr_process_required")
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
