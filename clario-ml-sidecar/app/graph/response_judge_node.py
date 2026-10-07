"""LLM judge scoring. Also the gate of the evaluator-optimizer loop: a weak score sets
judge_needs_revision (graph_builder sends it to reflection, bounded); never changes failure_type."""

from __future__ import annotations

import logging
import os

from app.graph.state import TicketState
from app.tools.few_shot_selector import select_few_shots
from app.tools.redaction_tool import mask_pii
from app.tools.response_judge import evaluate_draft

logger = logging.getLogger(__name__)

_DIMENSIONS = (
    "priority_tone_match_score", "completeness_score", "accuracy_score",
    "policy_compliance_score", "groundedness_score",
)


def judge_feedback(evaluation: dict) -> str | None:
    """The judge's own critique if the draft is below the revision bar, else None.

    Bar (rubric anchors in response_judge.py): overall below 4 means "has a real
    gap a reviewer would want fixed first"; any single dimension below 3 means a
    customer-visible problem (wrong info, missing part, tone mismatch).
    """
    min_overall = int(os.getenv("JUDGE_REVISION_MIN_OVERALL", "4"))
    min_dimension = int(os.getenv("JUDGE_REVISION_MIN_DIMENSION", "3"))
    overall = evaluation.get("overall_score")
    weak = [f"{name.removesuffix('_score').replace('_', ' ')} {evaluation[name]}/5"
            for name in _DIMENSIONS if isinstance(evaluation.get(name), int) and evaluation[name] < min_dimension]
    if not (isinstance(overall, int) and overall < min_overall) and not weak:
        return None
    parts = [f"overall {overall}/5", *weak]
    feedback = f"The quality judge scored this reply {', '.join(parts)}."
    if evaluation.get("reasoning"):
        feedback += f" Why: {evaluation['reasoning']}"
    suggestions = [s for s in evaluation.get("improvement_suggestions") or [] if s]
    if suggestions:
        feedback += " Fix: " + "; ".join(suggestions)
    return feedback


async def response_judge_node(state: TicketState) -> TicketState:
    """Score every drafted domain with the configured judge LLM and few-shot references.

    Runs for both cache-hit and freshly-drafted resolutions, right before
    escalation, so every final draft gets a stored evaluation regardless of
    which path produced it. Failures here never change failure_type/routing -
    this node only attaches judge_evaluations for the dashboard/Supabase.

    For a domain that went through reflection, this also scores the original
    pre-reflection draft (saved by reflection_node) and keeps whichever of the
    two actually scores higher - a real-data evaluation found reflection's own
    internal pass/fail check disagrees with this judge often enough that
    always accepting the rewrite made some replies measurably worse than the
    one that was already there. Doubles the judge call for a reflected domain
    only; every other domain is unaffected.
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
    reflected = state.get("reflection_count", 0) > 0
    pre_reflection_drafts = state.get("pre_reflection_drafts", {})

    evaluations: dict[str, dict] = {}
    final_drafts: dict[str, str] = {}
    llm_call_count = state.get("llm_call_count", 0)
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
            llm_call_count += score.attempts_used
            best_draft, best_score = draft, score

            pre_draft = pre_reflection_drafts.get(domain)
            pre_reflection_score = None
            kept_pre_reflection_draft = False
            if reflected and pre_draft and pre_draft != draft:
                try:
                    pre_score = await evaluate_draft(
                        pre_draft, priority, category, ticket_issue, few_shots,
                        retrieved_context.get(domain, []),
                    )
                    llm_call_count += pre_score.attempts_used
                    pre_reflection_score = pre_score.overall_score
                    if pre_score.overall_score > best_score.overall_score:
                        best_draft, best_score = pre_draft, pre_score
                        kept_pre_reflection_draft = True
                except Exception as e:
                    logger.warning(f"Pre-reflection re-score failed for domain={domain}: {e}")

            evaluation = best_score.to_dict()
            if pre_reflection_score is not None:
                # Otherwise-discarded once the fallback decision is made - kept here
                # so a later audit can see which of the two scores this ticket's
                # decision actually rested on, instead of a verification script
                # having to re-score the pre-reflection draft itself (a second,
                # independently-sampled judge call, at a nonzero temperature, that
                # can legitimately disagree with this one on the same text).
                evaluation["pre_reflection_score"] = pre_reflection_score
                evaluation["kept_pre_reflection_draft"] = kept_pre_reflection_draft
            evaluations[domain] = evaluation
            final_drafts[domain] = best_draft
        except Exception as e:
            logger.warning(f"Response judge failed for domain={domain}: {e}")
            llm_call_count += getattr(e, "attempts", 0)

    updated_drafts = {**drafts, **final_drafts}
    feedback = {domain: text for domain, evaluation in evaluations.items()
                if (text := judge_feedback(evaluation))}
    return {**state, "agent_drafts": updated_drafts, "judge_evaluations": evaluations,
            "judge_feedback": feedback, "judge_needs_revision": bool(feedback),
            "llm_call_count": llm_call_count}
