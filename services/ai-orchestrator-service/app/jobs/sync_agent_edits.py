"""Learns from human edits to escalated drafts.

Runs every 24h (see app/jobs/learning_schedule.py), behind
AGENT_EDIT_LEARNING_ENABLED. For each human_reviews row the API marked
'edited' (the agent changed the AI draft before sending), one LLM call
classifies the edit (factual vs style) and rewrites it as a generalized,
PII-free takeaway, stored in the agent_edit_refs collection. The LLM only ever
sees masked text, and a takeaway that still contains PII is rejected.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from app.tools.agent_edit_store import FLAG, upsert_agent_edit
from app.tools.feedback_learning import (
    contains_pii,
    customer_section,
    feature_enabled,
    first_row,
    get_supabase as _get_supabase,
    issue_text,
    masked,
    normalize_ws,
)

logger = logging.getLogger(__name__)

_MAX_TAKEAWAY_CHARS = 300
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_SELECT = (
    "id, original_draft, final_draft, decision, reviewed_at, tickets(id, raw_text, "
    "ticket_classifications(category, priority, sentiment), ticket_drafts(domain))"
)
_PROMPT = """You compare an AI-drafted customer-support reply with the version a human agent actually sent.
Decide what the agent's edit teaches, and write it as ONE generalized, self-contained sentence that would help draft future replies to DIFFERENT customers.

Rules:
- edit_type "factual": the agent corrected or added a fact, policy, step, or time frame. edit_type "style": the agent only changed tone, wording, structure, or empathy.
- The takeaway must NOT contain names, emails, order or ticket numbers, amounts, dates, or any detail specific to this one customer.
- Maximum 250 characters.

Ticket:
{issue}

AI draft:
{original}

Agent's final reply:
{final}

Respond with JSON only: {{"edit_type": "factual" | "style", "takeaway": "<sentence>"}}"""


def _llm(prompt: str) -> str:
    from app.tools.local_llm import llm_invoke

    return llm_invoke(prompt, temperature=0.0)


def sync_agent_edits(lookback_hours: int = 24) -> dict:
    summary = {"considered": 0, "synced": 0, "skipped": 0}
    if not feature_enabled(FLAG):
        return {**summary, "disabled": True}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    try:
        reviews = (
            _get_supabase().table("human_reviews").select(_SELECT)
            .eq("decision", "edited").gte("reviewed_at", cutoff).execute().data or []
        )
    except Exception as e:
        logger.error(f"Failed to fetch edited reviews: {e}")
        return summary

    summary["considered"] = len(reviews)
    for review in reviews:
        try:
            synced = _sync_one(review)
        except Exception as e:
            logger.warning(f"Failed to learn from review {review.get('id')}: {e}")
            synced = False
        summary["synced" if synced else "skipped"] += 1

    logger.info(f"Agent-edit sync: {summary}")
    return summary


def _sync_one(review: dict) -> bool:
    ticket = review.get("tickets")
    original = customer_section(review.get("original_draft"))
    final = (review.get("final_draft") or "").strip()
    if not isinstance(ticket, dict) or not original or not final:
        return False

    issue = masked(issue_text(ticket.get("raw_text")))
    original_masked, final_masked = masked(original), masked(final)
    if not issue or normalize_ws(original_masked) == normalize_ws(final_masked):
        return False

    verdict = _classify_edit(issue, original_masked, final_masked)
    if verdict is None:
        return False

    classification = first_row(ticket.get("ticket_classifications"))
    upsert_agent_edit(
        review_id=review["id"],
        issue_text=issue,
        takeaway=verdict["takeaway"],
        edit_type=verdict["edit_type"],
        domain=first_row(ticket.get("ticket_drafts")).get("domain") or "technical",
        category=classification.get("category") or "Unknown",
        priority=classification.get("priority") or "Unknown",
        sentiment=classification.get("sentiment") or "Unknown",
    )
    return True


def _classify_edit(issue: str, original: str, final: str) -> dict | None:
    raw = _llm(_PROMPT.format(issue=issue, original=original, final=final))
    try:
        data = json.loads(_FENCE.sub("", raw.strip()))
    except ValueError:
        return None
    edit_type = data.get("edit_type") if isinstance(data, dict) else None
    takeaway = str(data.get("takeaway", "")).strip() if isinstance(data, dict) else ""
    if edit_type not in {"factual", "style"} or not takeaway:
        return None
    if len(takeaway) > _MAX_TAKEAWAY_CHARS or contains_pii(takeaway):
        return None
    return {"edit_type": edit_type, "takeaway": takeaway}
