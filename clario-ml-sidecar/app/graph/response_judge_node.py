"""LLM judge scoring; record-only quality signal, does not affect failure_type."""

from __future__ import annotations

import logging

from app.graph.state import TicketState
from app.tools.few_shot_selector import select_few_shots
from app.tools.redaction_tool import mask_pii
from app.tools.response_judge import evaluate_draft

logger = logging.getLogger(__name__)


async def response_judge_node(state: TicketState) -> TicketState:
    """Score every drafted domain with the configured judge LLM and few-shot references.

    Runs for both cache-hit and freshly-drafted resolutions, right before
    escalation, so every final draft gets a stored evaluation regardless of
    which path produced it. Failures here never change failure_type/routing -
    this node only attaches judge_evaluations for the dashboard/Supabase.
    """
    drafts = state.get("agent_drafts", {})
    if not drafts:
        return {**state}

    # Cache-hit tickets skip surrogate_node, so redacted_text is never set.
    # Redact here too so the raw customer text never reaches the judge LLM.
    ticket_issue = state.get("redacted_text")
    if not ticket_issue:
        ticket_issue, _ = mask_pii(state.get("raw_text", ""))

    priority = state.get("priority") or "Medium"
    category = state.get("category") or "Unknown"
    retrieved_context = state.get("retrieved_context", {})

    evaluations: dict[str, dict] = {}
    for domain, draft in drafts.items():
        if not draft:
            continue
        judge_domain = domain if domain in ("technical", "billing") else "technical"
        try:
            few_shots = await select_few_shots(ticket_issue, priority, judge_domain)
        except Exception as e:
            logger.warning(f"Few-shot selection failed for domain={domain}: {e}")
            few_shots = []
        try:
            score = await evaluate_draft(
                draft,
                priority,
                category,
                ticket_issue,
                few_shots,
                retrieved_context.get(domain, []),
            )
            evaluations[domain] = score.to_dict()
        except Exception as e:
            logger.warning(f"Response judge failed for domain={domain}: {e}")

    return {**state, "judge_evaluations": evaluations}
