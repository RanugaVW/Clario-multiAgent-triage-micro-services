"""Billing specialist: retrieve context, assess relevance, then draft."""

import asyncio

from app.agents.shared.prompt_templates import build_specialist_prompt
from app.graph.state import TicketState
from app.tools.agent_edit_store import factual_context_items, format_edit_guidance, select_agent_edits
from app.tools.llm_client import generate
from app.tools.circuit_breaker import CircuitBreakerOpenError
from app.tools.rag_tool import check_relevance, retrieve_context, rewrite_query, search_with_correction


async def billing_agent_node(state: TicketState) -> TicketState:
    """Write Billing context, relevance data, and a draft or None on LLM failure."""
    domain = "billing"
    try:
        context, correction, rewrite_calls = await asyncio.to_thread(
            search_with_correction, state["redacted_text"], domain, retrieve_context, rewrite_query,
            state.get("corrective_rag", {}).get(domain),
        )
    except CircuitBreakerOpenError:
        return {**state, "agent_drafts": {**state.get("agent_drafts", {}), domain: None},
                "retrieved_context": {**state.get("retrieved_context", {}), domain: []},
                "rag_top_score": {**state.get("rag_top_score", {}), domain: 0.0},
                "low_relevance_flags": {**state.get("low_relevance_flags", {}), domain: True},
                "failure_type": "dependency_failure"}
    top_score = float(context[0]["score"]) if context else 0.0
    edits = select_agent_edits(state["redacted_text"], domain)
    context = [*context, *factual_context_items(edits)]
    prior_critique = state["reflection_critiques"][-1] if state.get("reflection_count", 0) else None
    prompt = build_specialist_prompt(
        state["redacted_text"], context, domain, prior_critique,
        extra_instructions=format_edit_guidance(edits),
        priority=state.get("priority"), sentiment=state.get("sentiment"),
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
        "corrective_rag": {**state.get("corrective_rag", {}), **({domain: correction} if correction else {})},
        "llm_call_count": state.get("llm_call_count", 0) + calls_made + rewrite_calls,
    }
