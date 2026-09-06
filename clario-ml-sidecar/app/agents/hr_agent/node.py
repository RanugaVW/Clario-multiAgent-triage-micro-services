"""HR specialist: retrieve context, assess relevance, then draft - always
mandatorily escalated afterward (see escalation_node.py's decide_escalation),
so this draft is a starting point for a human reviewer, never auto-sent."""

from app.agents.shared.prompt_templates import build_specialist_prompt
from app.graph.state import TicketState
from app.tools.llm_client import generate
from app.tools.circuit_breaker import CircuitBreakerOpenError
from app.tools.rag_tool import check_relevance, retrieve_context

_HR_EXTRA_INSTRUCTIONS = (
    "Do not promise a specific outcome (a refund amount, approval, or timeline) - "
    "this ticket requires human review before any decision is made. Acknowledge "
    "the issue, explain what will be reviewed, and set expectations for next "
    "steps only."
)


async def hr_agent_node(state: TicketState) -> TicketState:
    """Write HR context, relevance data, and a draft or None on LLM failure."""
    domain = "hr"
    try:
        context = retrieve_context(state["redacted_text"], domain)
    except CircuitBreakerOpenError:
        return {**state, "agent_drafts": {**state.get("agent_drafts", {}), domain: None},
                "retrieved_context": {**state.get("retrieved_context", {}), domain: []},
                "rag_top_score": {**state.get("rag_top_score", {}), domain: 0.0},
                "low_relevance_flags": {**state.get("low_relevance_flags", {}), domain: True},
                "failure_type": "dependency_failure"}
    top_score = float(context[0]["score"]) if context else 0.0
    prior_critique = state["reflection_critiques"][-1] if state.get("reflection_count", 0) else None
    prompt = build_specialist_prompt(
        state["redacted_text"], context, domain, prior_critique, _HR_EXTRA_INSTRUCTIONS
    )
    try:
        draft, calls_made = await generate(prompt)
    except (RuntimeError, CircuitBreakerOpenError) as err:
        draft = None
        calls_made = getattr(err, "attempts", 0)
    return {
        **state,
        "agent_drafts": {**state.get("agent_drafts", {}), domain: draft},
        "retrieved_context": {**state.get("retrieved_context", {}), domain: context},
        "rag_top_score": {**state.get("rag_top_score", {}), domain: top_score},
        "low_relevance_flags": {
            **state.get("low_relevance_flags", {}), domain: draft is None or not check_relevance(context)
        },
        "failure_type": "dependency_failure" if draft is None else state.get("failure_type", "none"),
        "llm_call_count": state.get("llm_call_count", 0) + calls_made,
    }
