"""Build bounded revision feedback for the same specialist that drafted the response."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.graph.state import TicketState

load_dotenv()


def reflection_node(state: TicketState) -> TicketState:
    """Append a critique for quality/policy only; never call this for misroute/dependency failure."""
    if state.get("failure_type") not in {"quality", "policy"}:
        raise ValueError("reflection is only valid for quality or policy failures")
    max_attempts = int(os.getenv("MAX_REFLECTION_ATTEMPTS", "2"))
    if state.get("reflection_count", 0) >= max_attempts:
        raise ValueError("reflection attempt cap has been reached")
    critiques = []
    for domain, result in state.get("validation_result", {}).items():
        if result.get("passed", False):
            continue
        reasons = ", ".join(result.get("failed_rules", [])) or "judge rejected the draft"
        judge_reasoning = result.get("judge_reasoning") or result.get("reasoning")
        detail = f"{domain}: failed {reasons}"
        critiques.append(f"{detail}; judge: {judge_reasoning}" if judge_reasoning else detail)
    critique = " | ".join(critiques) or "Revise the response to satisfy validation requirements."
    return {
        **state,
        "reflection_count": state.get("reflection_count", 0) + 1,
        "reflection_critiques": [*state.get("reflection_critiques", []), critique],
    }
